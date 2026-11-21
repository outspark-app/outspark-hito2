from outspark.shared.domain.value_objects import identifier


class ImportedProfiles:
    def __init__(self, repository):
        self.repository = repository

    def provision(self, users, source):
        identifier(source)
        for user in users:
            identifier(user["user_id"])
            if (
                isinstance(user["node_id"], bool)
                or not isinstance(user["node_id"], int)
                or user["node_id"] < 0
                or user["user_id"] != f"fb-{user['node_id']}"
            ):
                raise ValueError("Cuenta de simulación histórica no válida.")
        return self.repository.provision_imported(users, source)
