from outspark.communities.interfaces.acl.facade import CommunitiesFacade


class CommunityPermits:
    def __init__(self, facade: CommunitiesFacade):
        self.facade = facade

    def topics(self, topics):
        return self.facade.validate_topics(topics)

    def permit(self, actor, community, topics):
        return self.facade.publishing_permit(actor, community, topics)
