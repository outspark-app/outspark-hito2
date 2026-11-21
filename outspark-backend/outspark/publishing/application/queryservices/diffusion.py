from outspark.shared.application.errors import UseCaseError


class PublicationDiffusion:
    def __init__(self, publications, network):
        self.publications = publications
        self.network = network

    def preview(self, publication_id, actor, options):
        publication = self.publications.original(publication_id, active=True)
        if publication["author_id"] != actor:
            raise UseCaseError(
                403, "author_required", "Solo el autor puede simular esta publicación."
            )
        return {
            "publication_id": publication_id,
            **self.network.diffusion(actor, **options),
        }
