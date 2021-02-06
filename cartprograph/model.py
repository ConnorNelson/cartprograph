import json

from . import context


class RedisBackedObject:
    attributes = NotImplemented

    def __init__(self, *, redis_client=None, cached_graph=None, copy_from=None):
        if redis_client is None:
            redis_client = context["redis_client"]
        self.redis_client = redis_client
        if cached_graph is None:
            cached_graph = context["cached_graph"]
        self.cached_graph = cached_graph
        if copy_from:
            for name, value in copy_from:
                setattr(self, name, value)

    @property
    def cache(self):
        raise NotImplementedError()

    def invalidate(self, name=None, *, purge=False):
        attributes = self.attributes if name is None else [name]
        for attr in attributes:
            if not purge:
                setattr(self, attr, getattr(self, attr))
            else:
                del self.cache[attr]

    def __str__(self):
        raise NotImplementedError()

    def __getattr__(self, name):
        if name in self.attributes:
            try:
                value = self.cache[name]
            except KeyError:
                value = self.redis_client.get(f"{self}.{name}")
                if value is not None:
                    value = json.loads(value)
                self.cache[name] = value
            return value
        else:
            raise AttributeError()

    def __setattr__(self, name, value):
        if name in self.attributes:
            self.redis_client.set(f"{self}.{name}", json.dumps(value))
            self.cache[name] = value
        else:
            return super().__setattr__(name, value)

    def __iter__(self):
        for attr in self.attributes:
            yield attr, getattr(self, attr)


class FakeCache:
    def __getitem__(self, key):
        raise KeyError()

    def __setitem__(self, key, value):
        pass

    def __delitem__(self, key):
        pass


class Node(RedisBackedObject):
    attributes = ["parent_id", "basic_blocks", "syscalls", "interactions"]

    def __init__(self, id, **kwargs):
        self.id = id
        super().__init__(**kwargs)
        self.cache  # warm up the cache

    def __setattr__(self, name, value):
        if name == "parent_id":
            parent_id = value
            if parent_id is not None:
                self.cached_graph.add_edge(parent_id, self.id)
        return super().__setattr__(name, value)

    @property
    def cache(self):
        if self.cached_graph is None:
            return FakeCache()
        if self.id not in self.cached_graph.nodes:
            self.cached_graph.add_node(self.id)
        return self.cached_graph.nodes[self.id]

    def __str__(self):
        return f"node.{self.id}"
