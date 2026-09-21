import dataclasses
import heapq


@dataclasses.dataclass(frozen=True, order=True)
class Edge:
    weight: float
    target: str


class ShortestConventionPath:
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
