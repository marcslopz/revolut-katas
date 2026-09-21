import dataclasses
import heapq


@dataclasses.dataclass(frozen=True, order=True)
class Edge:
    weight: float
    target: str


class ShortestConversionPath:
    def __init__(self):
        self._graph: dict[str, list[Edge]] = dict()

    def add_conversion(
        self, from_currency: str, to_currency: str, weight: float
    ) -> None:
        if from_currency not in self._graph:
            self._graph[from_currency] = list()
        self._graph[from_currency].append(Edge(weight, to_currency))

    def cheapest_path(
        self, from_currency: str, to_currency: str
    ) -> tuple[float, list[str]]:
        if from_currency not in self._graph:
            raise KeyError("Currency source not found in graph", from_currency)
        current_min_weight = {from_currency: 0}
        edges_to_check = []
        heapq.heappush(edges_to_check, Edge(0.0, from_currency))
        path_dict = {}
        while edges_to_check:
            current_edge = heapq.heappop(edges_to_check)
            if current_edge.target == to_currency:
                break
            if current_edge.weight > current_min_weight.get(
                current_edge.target, float("inf")
            ):
                continue
            for neighbor_edge in self._graph.get(current_edge.target, []):
                new_dist = current_edge.weight + neighbor_edge.weight
                if new_dist < current_min_weight.get(
                    neighbor_edge.target, float("inf")
                ):
                    current_min_weight[neighbor_edge.target] = new_dist
                    path_dict[neighbor_edge.target] = current_edge.target
                    heapq.heappush(edges_to_check, Edge(new_dist, neighbor_edge.target))
        if to_currency not in path_dict:
            return float("inf"), []
        path = [to_currency]
        current = to_currency
        while current != from_currency:
            current = path_dict[current]
            path.append(current)
        path.reverse()
        return current_min_weight[to_currency], path


class ShortestConversionPathWithNegative:
    def __init__(self):
        self._nodes: set[str] = set()
        self._edges: list[tuple[str, str, float]] = list()

    def add_conversion(
        self, from_currency: str, to_currency: str, weight: float
    ) -> None:
        self._nodes.add(from_currency)
        self._nodes.add(to_currency)
        self._edges.append((from_currency, to_currency, weight))

    def _pass(self, current_min_weight, path_dict) -> bool:
        edges_to_check = tuple(self._edges)
        dist_changed = False
        for edge in edges_to_check:
            current_from = edge[0]
            current_to = edge[1]
            current_weight = edge[2]
            candidate = (
                current_min_weight.get(current_from, float("inf")) + current_weight
            )
            if candidate < current_min_weight.get(current_to, float("inf")):
                current_min_weight[current_to] = candidate
                path_dict[current_to] = current_from
                dist_changed = True
        return dist_changed

    def cheapest_path(
        self, from_currency: str, to_currency: str
    ) -> tuple[float, list[str]]:
        if from_currency not in self._nodes:
            raise KeyError("Currency source not found in graph", from_currency)
        current_min_weight = {from_currency: 0.0}
        path_dict = {}

        for _ in range(len(self._nodes) - 1):
            dist_changed = self._pass(current_min_weight, path_dict)
            if not dist_changed:
                break

        dist_changed = self._pass(current_min_weight, path_dict)
        if dist_changed:
            raise ValueError("Negative edge loop")

        if to_currency not in path_dict:
            return float("inf"), []
        path = [to_currency]
        current = to_currency
        while current != from_currency:
            current = path_dict[current]
            path.append(current)
        path.reverse()
        return current_min_weight[to_currency], path
