from outspark.profiles.interfaces.acl.facade import ProfilesFacade


class ProfileActors:
    def __init__(self, facade: ProfilesFacade):
        self.facade = facade

    def active_guard(self, actor):
        return self.facade.actor(actor).active_guard
