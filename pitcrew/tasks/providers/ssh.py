from pitcrew import task
from netaddr.ip.nmap import iter_nmap_range


class SSHProvider:
    def __init__(self, context, hosts, user):
        self.context = context
        self.hosts = hosts
        self.flattened_hosts = list(
            map(lambda ip: str(ip), iter_nmap_range(*self.hosts))
        )
        self.user = user
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index == len(self.flattened_hosts):
            raise StopAsyncIteration
        ssh_ctx = self.context.ssh_context(
            host=self.flattened_hosts[self.index], user=self.user
        )
        self.index += 1
        return ssh_ctx

    def __str__(self):
        return f"SSHProvider(user={self.user} hosts={self.hosts})"


@task.returns("An async generator that gives ssh contexts")
@task.arg("user", type=str, desc="The user to use for the ssh contexts")
@task.arg("hosts", type=list, desc="The hosts to use for ssh contexts")
class ProvidersSsh(task.BaseTask):
    """A provider for ssh contexts"""

    async def run(self) -> SSHProvider:
        return SSHProvider(self.context, self.params.hosts, self.params.user)