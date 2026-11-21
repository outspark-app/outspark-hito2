from outspark.network_analysis.interfaces.acl.facade import NetworkFacade


class PublicationNetwork:
    def __init__(self, facade: NetworkFacade):
        self.facade = facade

    def diffusion(self, actor, **options):
        return self.facade.diffusion(actor, **options)
