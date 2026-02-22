class EvaluationCache:
    def __init__(self):
        self._seen = set()

    def seen(self, pr_number, head_sha, policy_hash):
        return (pr_number, head_sha, policy_hash) in self._seen

    def mark(self, pr_number, head_sha, policy_hash):
        self._seen.add((pr_number, head_sha, policy_hash))
