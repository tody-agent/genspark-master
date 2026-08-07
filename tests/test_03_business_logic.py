import pytest
from genspark_cli.account_router import AccountRouter, HEALTH_HEALTHY, HEALTH_COOLDOWN, HEALTH_EXPIRED, HEALTH_NEEDS_LOGIN

class MockProfileManager:
    def __init__(self, profiles_data):
        self._profiles = profiles_data
        self.default_profile = profiles_data[0]["name"] if profiles_data else None

    def list_profiles(self):
        return self._profiles

    def get_session(self, name):
        class MockSession:
            def __init__(self, profile_name):
                self.profile_name = profile_name
        return MockSession(name)

def test_account_router_failover_logic():
    """
    Layer 3: Verify AccountRouter properly handles failover and circuit breaking.
    """
    mock_data = [
        {"name": "test1", "is_logged_in": True, "cookie_health": "good"},
        {"name": "test2", "is_logged_in": True, "cookie_health": "good"},
    ]
    pm = MockProfileManager(mock_data)
    router = AccountRouter(pm)
    
    # Verify pool state
    assert router.pool_size == 2
    assert router.available_count == 2
    
    # 1. Test getting default session
    session1 = router.get_session()
    assert session1.profile_name == "test1"
    
    # 2. Simulate failure triggering failover
    router.mark_unhealthy("test1", cooldown=300)
    assert router.available_count == 1
    
    # Next session should be test2
    session2 = router.get_session()
    assert session2.profile_name == "test2"
    
    # 3. Simulate second failure
    router.mark_unhealthy("test2", cooldown=300)
    assert router.available_count == 0
    
    # 4. Total failure raises RuntimeError
    with pytest.raises(RuntimeError) as exc_info:
        router.get_session()
        
    assert "All accounts are in cooldown" in str(exc_info.value)
