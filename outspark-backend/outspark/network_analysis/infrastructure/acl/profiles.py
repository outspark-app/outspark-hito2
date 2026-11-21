from outspark.profiles.interfaces.acl.facade import ProfilesFacade

from ...domain.model.dataset import simulation_user


class ProfileProvisioning:
    def __init__(self, facade: ProfilesFacade):
        self.facade = facade

    def provision(self, nodes, source):
        return self.facade.provision_imported(
            [{"user_id": simulation_user(node), "node_id": node} for node in nodes], source
        )
