from outspark.communities.interfaces.acl.facade import CommunitiesFacade


class CommunityTopics:
    def __init__(self, facade: CommunitiesFacade):
        self.facade = facade

    def validate(self, topics):
        return self.facade.validate_topics(topics)
