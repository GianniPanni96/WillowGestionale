import ast
import html
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx
import pydot
from pyvis.network import Network


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "ArchitectureTools" / "output"
OUTPUT_JSON = OUTPUT_DIR / "class_dependencies.json"
OUTPUT_HTML = OUTPUT_DIR / "dependency_graph.html"
OUTPUT_SVG = OUTPUT_DIR / "dependency_graph.svg"
OUTPUT_DOT = OUTPUT_DIR / "dependency_graph.dot"
LEGACY_OUTPUT_MD = OUTPUT_DIR / "dependency_report.md"

EXCLUDED_DIRS = {
    ".git",
    ".idea",
    "__pycache__",
    "venv",
    "build",
    "dist",
}

FOCUS_DIRS = {
    "Views",
    "Controllerss",
    "QueryServices",
    "AnalyzerServices",
    "WarningServices",
    "Utils",
}

PACKAGE_COLORS = {
    "Views": "#3b82f6",
    "Controllerss": "#f97316",
    "QueryServices": "#10b981",
    "AnalyzerServices": "#eab308",
    "WarningServices": "#ef4444",
    "Utils": "#8b5cf6",
    "Model": "#64748b",
    "Config": "#06b6d4",
    "App_context": "#ec4899",
    "Other": "#6b7280",
}

EDGE_COLORS = {
    "inherits": "#f97316",
    "uses": "#94a3b8",
}


@dataclass
class ClassInfo:
    fqcn: str
    class_name: str
    module_name: str
    file_path: str
    package: str
    bases: set[str] = field(default_factory=set)
    uses: set[str] = field(default_factory=set)


def is_project_python_file(path: Path) -> bool:
    if path.suffix != ".py":
        return False
    if any(part in EXCLUDED_DIRS for part in path.parts):
        return False
    if path.name == "__init__.py":
        return False
    return True


def iter_project_files() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*.py") if is_project_python_file(path))


def module_name_from_path(path: Path) -> str:
    return ".".join(path.relative_to(ROOT).with_suffix("").parts)


def package_name_from_module(module_name: str) -> str:
    return module_name.split(".")[0]


def normalize_package_name(package_name: str) -> str:
    return package_name if package_name in PACKAGE_COLORS else "Other"


def build_class_index(files: list[Path]) -> dict[str, list[ClassInfo]]:
    class_index: dict[str, list[ClassInfo]] = defaultdict(list)
    for path in files:
        module_name = module_name_from_path(path)
        package_name = package_name_from_module(module_name)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                fqcn = f"{module_name}.{node.name}"
                class_index[node.name].append(
                    ClassInfo(
                        fqcn=fqcn,
                        class_name=node.name,
                        module_name=module_name,
                        file_path=str(path.relative_to(ROOT)),
                        package=normalize_package_name(package_name),
                    )
                )
    return class_index


def build_import_aliases(module_name: str, tree: ast.AST, class_index: dict[str, list[ClassInfo]]) -> dict[str, set[str]]:
    aliases: dict[str, set[str]] = defaultdict(set)
    current_package = package_name_from_module(module_name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_module = alias.name
                imported_package = imported_module.split(".")[0]
                if imported_package not in FOCUS_DIRS and imported_package != current_package:
                    continue
                local_name = alias.asname or imported_module.split(".")[-1]
                aliases[local_name].add(imported_module)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            imported_module = node.module
            imported_package = imported_module.split(".")[0]
            if imported_package not in FOCUS_DIRS and imported_package != current_package:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                local_name = alias.asname or alias.name
                fqcn = f"{imported_module}.{alias.name}"
                if alias.name in class_index:
                    aliases[local_name].add(fqcn)
                else:
                    aliases[local_name].add(imported_module)

    return aliases


def extract_name_from_expr(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return extract_name_from_expr(node.value)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp):
        return extract_name_from_expr(node.left) or extract_name_from_expr(node.right)
    return None


def resolve_class_references(name: str | None, aliases: dict[str, set[str]], class_index: dict[str, list[ClassInfo]]) -> set[str]:
    if not name:
        return set()

    resolved: set[str] = set()
    if name in aliases:
        for alias_target in aliases[name]:
            if alias_target in {info.fqcn for info in class_index.get(name, [])}:
                resolved.add(alias_target)
            elif alias_target in class_index:
                resolved.update(info.fqcn for info in class_index[alias_target])
            else:
                maybe_class_name = alias_target.split(".")[-1]
                if maybe_class_name in class_index:
                    resolved.update(info.fqcn for info in class_index[maybe_class_name])

    if not resolved and name in class_index:
        resolved.update(info.fqcn for info in class_index[name])

    return resolved


def extract_self_dependency_names(class_node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(class_node):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Attribute):
            if isinstance(node.target.value, ast.Name) and node.target.value.id == "self":
                names.add(extract_name_from_expr(node.annotation))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                    if isinstance(node.value, ast.Call):
                        names.add(extract_name_from_expr(node.value.func))
                    elif isinstance(node.value, ast.Name):
                        names.add(node.value.id)
        elif isinstance(node, ast.Call):
            names.add(extract_name_from_expr(node.func))
    return {name for name in names if name}


def build_class_map(files: list[Path], class_index: dict[str, list[ClassInfo]]) -> dict[str, ClassInfo]:
    class_map: dict[str, ClassInfo] = {}

    for path in files:
        module_name = module_name_from_path(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        aliases = build_import_aliases(module_name, tree, class_index)

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue

            fqcn = f"{module_name}.{node.name}"
            class_info = next(info for info in class_index[node.name] if info.fqcn == fqcn)

            for base in node.bases:
                class_info.bases.update(resolve_class_references(extract_name_from_expr(base), aliases, class_index))

            for dependency_name in extract_self_dependency_names(node):
                class_info.uses.update(resolve_class_references(dependency_name, aliases, class_index))

            class_info.bases.discard(class_info.fqcn)
            class_info.uses.discard(class_info.fqcn)
            class_map[fqcn] = class_info

    return class_map


def build_graph(class_map: dict[str, ClassInfo]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for fqcn, info in class_map.items():
        graph.add_node(
            fqcn,
            label=info.class_name,
            module=info.module_name,
            package=info.package,
            file_path=info.file_path,
        )

    for fqcn, info in class_map.items():
        for base in sorted(info.bases):
            if base in class_map:
                graph.add_edge(fqcn, base, relation="inherits")
        for target in sorted(info.uses):
            if target in class_map:
                graph.add_edge(fqcn, target, relation="uses")

    return graph


def build_module_graph(graph: nx.DiGraph) -> dict[str, set[str]]:
    module_edges: dict[str, set[str]] = defaultdict(set)
    for source, target in graph.edges():
        source_module = graph.nodes[source]["module"]
        target_module = graph.nodes[target]["module"]
        if source_module != target_module:
            module_edges[source_module].add(target_module)
    return module_edges


def find_cycles(module_graph: dict[str, set[str]]) -> list[list[str]]:
    visited: set[str] = set()
    stack: list[str] = []
    active: set[str] = set()
    cycles: set[tuple[str, ...]] = set()

    def dfs(node: str) -> None:
        visited.add(node)
        active.add(node)
        stack.append(node)

        for neighbor in sorted(module_graph.get(node, set())):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in active:
                start = stack.index(neighbor)
                cycles.add(tuple(stack[start:] + [neighbor]))

        stack.pop()
        active.remove(node)

    for node in sorted(module_graph):
        if node not in visited:
            dfs(node)

    return [list(cycle) for cycle in sorted(cycles)]


def ensure_connected_for_layout(graph: nx.DiGraph) -> nx.Graph:
    undirected = graph.to_undirected()
    if undirected.number_of_nodes() <= 1:
        return undirected

    components = list(nx.connected_components(undirected))
    if len(components) <= 1:
        return undirected

    previous_anchor = None
    for component in components:
        anchor = sorted(component)[0]
        if previous_anchor is not None:
            undirected.add_edge(previous_anchor, anchor)
        previous_anchor = anchor

    return undirected


def compute_positions(graph: nx.DiGraph) -> dict[str, tuple[float, float]]:
    if graph.number_of_nodes() == 0:
        return {}

    package_order = [package for package in PACKAGE_COLORS if package != "Other"]
    package_order.extend(
        sorted(
            {
                graph.nodes[node]["package"]
                for node in graph.nodes()
                if graph.nodes[node]["package"] not in package_order
            }
        )
    )

    column_width = 540
    module_indent = 36
    row_height = 78
    module_gap = 34
    package_gap = 90
    padding_x = 180
    padding_y = 140

    positions: dict[str, tuple[float, float]] = {}

    for package_index, package in enumerate(package_order):
        package_nodes = sorted(
            [node for node in graph.nodes() if graph.nodes[node]["package"] == package],
            key=lambda node: (
                graph.nodes[node]["module"].casefold(),
                graph.nodes[node]["label"].casefold(),
            ),
        )
        if not package_nodes:
            continue

        module_groups: dict[str, list[str]] = defaultdict(list)
        for node in package_nodes:
            module_groups[graph.nodes[node]["module"]].append(node)

        current_y = padding_y
        base_x = padding_x + package_index * column_width

        for module_name in sorted(module_groups, key=str.casefold):
            module_nodes = module_groups[module_name]
            for row_index, node in enumerate(module_nodes):
                x = base_x + module_indent * (row_index % 2)
                y = current_y + row_index * row_height
                positions[node] = (x, y)

            current_y += len(module_nodes) * row_height + module_gap

        current_y += package_gap

    return positions


def build_json_payload(class_map: dict[str, ClassInfo], graph: nx.DiGraph, positions: dict[str, tuple[float, float]], module_graph: dict[str, set[str]]) -> dict:
    return {
        "classes": {
            fqcn: {
                "class_name": info.class_name,
                "module_name": info.module_name,
                "file_path": info.file_path,
                "package": info.package,
                "bases": sorted(info.bases),
                "uses": sorted(info.uses),
                "position": {"x": positions[fqcn][0], "y": positions[fqcn][1]},
            }
            for fqcn, info in sorted(class_map.items())
        },
        "edges": [
            {
                "source": source,
                "target": target,
                "relation": graph.edges[source, target]["relation"],
            }
            for source, target in sorted(graph.edges())
        ],
        "module_cycles": find_cycles(module_graph),
    }


def write_dot(graph: nx.DiGraph) -> None:
    dot_graph = pydot.Dot(graph_type="digraph", rankdir="LR", bgcolor="#0f172a")

    for package in sorted({graph.nodes[node]["package"] for node in graph.nodes()}):
        cluster = pydot.Cluster(
            graph_name=f"cluster_{package}",
            label=package,
            color=PACKAGE_COLORS.get(package, PACKAGE_COLORS["Other"]),
            style="rounded",
            fontcolor="white",
            fontsize="18",
        )

        for node in sorted(node for node in graph.nodes() if graph.nodes[node]["package"] == package):
            attrs = graph.nodes[node]
            cluster.add_node(
                pydot.Node(
                    node,
                    label=attrs["label"],
                    shape="box",
                    style="filled,rounded",
                    fillcolor=PACKAGE_COLORS.get(attrs["package"], PACKAGE_COLORS["Other"]),
                    fontcolor="white",
                    color="#111827",
                )
            )
        dot_graph.add_subgraph(cluster)

    for source, target, data in graph.edges(data=True):
        dot_graph.add_edge(
            pydot.Edge(
                source,
                target,
                color=EDGE_COLORS[data["relation"]],
                penwidth="2.2" if data["relation"] == "inherits" else "1.2",
                label=data["relation"],
                fontcolor=EDGE_COLORS[data["relation"]],
            )
        )

    OUTPUT_DOT.write_text(dot_graph.to_string(), encoding="utf-8")


def render_svg(graph: nx.DiGraph, positions: dict[str, tuple[float, float]]) -> str:
    node_width = 180
    node_height = 34
    margin = 120

    xs = [positions[node][0] for node in graph.nodes()]
    ys = [positions[node][1] for node in graph.nodes()]
    width = int(max(xs, default=500) + margin)
    height = int(max(ys, default=500) + margin)

    package_boxes: dict[str, dict[str, float]] = {}
    for package in {graph.nodes[node]["package"] for node in graph.nodes()}:
        package_nodes = [node for node in graph.nodes() if graph.nodes[node]["package"] == package]
        if not package_nodes:
            continue
        package_xs = [positions[node][0] for node in package_nodes]
        package_ys = [positions[node][1] for node in package_nodes]
        package_boxes[package] = {
            "x": min(package_xs) - node_width / 2 - 30,
            "y": min(package_ys) - node_height / 2 - 55,
            "width": max(package_xs) - min(package_xs) + node_width + 60,
            "height": max(package_ys) - min(package_ys) + node_height + 90,
        }

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs>',
        '<marker id="arrow-uses" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">',
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8"/>',
        '</marker>',
        '<marker id="arrow-inherits" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">',
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#f97316"/>',
        '</marker>',
        '</defs>',
        '<rect width="100%" height="100%" fill="#020617"/>',
    ]

    for package, box in sorted(package_boxes.items()):
        color = PACKAGE_COLORS.get(package, PACKAGE_COLORS["Other"])
        parts.append(
            f'<rect x="{box["x"]:.1f}" y="{box["y"]:.1f}" width="{box["width"]:.1f}" height="{box["height"]:.1f}" '
            f'rx="22" ry="22" fill="#0f172a" stroke="{color}" stroke-width="2"/>'
        )
        parts.append(
            f'<text x="{box["x"] + 18:.1f}" y="{box["y"] + 28:.1f}" fill="{color}" font-family="Segoe UI" font-size="18" font-weight="bold">{html.escape(package)}</text>'
        )

    for source, target, data in graph.edges(data=True):
        sx, sy = positions[source]
        tx, ty = positions[target]
        color = EDGE_COLORS[data["relation"]]
        marker = f'url(#arrow-{data["relation"]})'
        parts.append(
            f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" stroke="{color}" stroke-width="{"2.4" if data["relation"] == "inherits" else "1.4"}" marker-end="{marker}" opacity="0.75"/>'
        )

    for node in graph.nodes():
        attrs = graph.nodes[node]
        x, y = positions[node]
        color = PACKAGE_COLORS.get(attrs["package"], PACKAGE_COLORS["Other"])
        rect_x = x - node_width / 2
        rect_y = y - node_height / 2
        parts.append(
            f'<rect x="{rect_x:.1f}" y="{rect_y:.1f}" width="{node_width}" height="{node_height}" rx="10" ry="10" fill="{color}" stroke="#111827" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{y + 5:.1f}" fill="white" font-family="Segoe UI" font-size="13" font-weight="600" text-anchor="middle">{html.escape(attrs["label"])}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def render_pyvis_html(graph: nx.DiGraph, positions: dict[str, tuple[float, float]]) -> str:
    present_packages = [
        package for package in PACKAGE_COLORS
        if any(graph.nodes[node]["package"] == package for node in graph.nodes())
    ]
    extra_packages = sorted(
        {
            graph.nodes[node]["package"]
            for node in graph.nodes()
            if graph.nodes[node]["package"] not in present_packages
        }
    )
    present_packages.extend(extra_packages)

    net = Network(
        height="100vh",
        width="100%",
        bgcolor="#020617",
        font_color="white",
        directed=True,
        cdn_resources="in_line",
    )

    net.barnes_hut(gravity=-15000, central_gravity=0.15, spring_length=180, spring_strength=0.02, damping=0.25)
    net.set_options("""
    const options = {
      "physics": {
        "enabled": false
      },
      "interaction": {
        "hover": true,
        "dragNodes": true,
        "dragView": true,
        "navigationButtons": true,
        "keyboard": true
      },
      "layout": {
        "improvedLayout": false
      }
    }
    """)

    for node in graph.nodes():
        attrs = graph.nodes[node]
        x, y = positions[node]
        color = PACKAGE_COLORS.get(attrs["package"], PACKAGE_COLORS["Other"])
        net.add_node(
            node,
            label=attrs["label"],
            title=f"<b>{html.escape(attrs['label'])}</b><br>{html.escape(attrs['module'])}<br>{html.escape(attrs['file_path'])}",
            color={
                "background": color,
                "border": color,
                "highlight": {
                    "background": color,
                    "border": "#f8fafc",
                },
                "hover": {
                    "background": color,
                    "border": "#e2e8f0",
                },
            },
            shape="box",
            x=x,
            y=y,
            physics=False,
            fixed={"x": False, "y": False},
            group=attrs["package"],
            borderWidth=1,
            borderWidthSelected=3,
        )

    for source, target, data in graph.edges(data=True):
        color = EDGE_COLORS[data["relation"]]
        net.add_edge(
            source,
            target,
            title=data["relation"],
            color=color,
            width=3 if data["relation"] == "inherits" else 1.5,
            arrows="to",
            dashes=data["relation"] == "uses",
        )

    html_output = net.generate_html(notebook=False)
    injection = """
<style>
body { margin: 0; font-family: Segoe UI, sans-serif; background: #020617; }
.toolbar {
  position: fixed; top: 12px; left: 12px; z-index: 1000;
  background: rgba(15, 23, 42, 0.92); color: white; padding: 12px 14px;
  border: 1px solid #1e293b; border-radius: 12px; width: 320px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.35);
}
.toolbar h1 { font-size: 16px; margin: 0 0 10px 0; }
.toolbar input {
  width: 100%; padding: 8px 10px; border-radius: 8px; border: 1px solid #334155;
  background: #0f172a; color: white; box-sizing: border-box; margin-bottom: 10px;
}
.legend { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 10px; font-size: 12px; }
.legend-item { display: flex; align-items: center; gap: 8px; }
.legend-item label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.legend-item input { accent-color: #e2e8f0; margin: 0; }
.swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
</style>
<div class="toolbar">
  <h1>Dependency Graph</h1>
  <input id="nodeSearch" type="text" placeholder="Cerca classe o modulo..." />
  <div class="legend">
"""
    for package in present_packages:
        color = PACKAGE_COLORS.get(package, PACKAGE_COLORS["Other"])
        package_id = html.escape(package)
        injection += (
            f'<div class="legend-item">'
            f'<label>'
            f'<input type="checkbox" class="package-filter" value="{package_id}" checked />'
            f'<span class="swatch" style="background:{color}"></span>'
            f'<span>{package_id}</span>'
            f'</label>'
            f'</div>'
        )
    injection += """
  </div>
</div>
<script>
window.addEventListener("load", function () {
  const input = document.getElementById("nodeSearch");
  const packageCheckboxes = Array.from(document.querySelectorAll(".package-filter"));
  if (!input || typeof network === "undefined" || typeof nodes === "undefined" || typeof edges === "undefined") return;

  const originalNodes = nodes.get();
  const originalEdges = edges.get();
  const nodesById = new Map(originalNodes.map(node => [node.id, node]));
  const adjacency = new Map();

  nodes.update(originalNodes.map(node => ({
    id: node.id,
    fixed: false
  })));
  network.fit({ animation: false });

  function ensureSet(nodeId) {
    if (!adjacency.has(nodeId)) {
      adjacency.set(nodeId, new Set());
    }
    return adjacency.get(nodeId);
  }

  originalEdges.forEach(edge => {
    ensureSet(edge.from).add(edge.to);
    ensureSet(edge.to).add(edge.from);
  });

  function getSelectedPackages() {
    return new Set(
      packageCheckboxes
        .filter(checkbox => checkbox.checked)
        .map(checkbox => checkbox.value)
    );
  }

  function getReachableIds(seedIds, allowedPackages) {
    const visited = new Set();
    const queue = Array.from(seedIds);

    while (queue.length > 0) {
      const nodeId = queue.shift();
      if (visited.has(nodeId)) {
        continue;
      }

      const node = nodesById.get(nodeId);
      if (!node || !allowedPackages.has(node.group)) {
        continue;
      }

      visited.add(nodeId);
      const neighbors = adjacency.get(nodeId) || new Set();
      neighbors.forEach(neighborId => {
        if (!visited.has(neighborId)) {
          queue.push(neighborId);
        }
      });
    }

    return visited;
  }

  function applyFilters() {
    const term = input.value.trim().toLowerCase();
    const selectedPackages = getSelectedPackages();
    const packageVisibleIds = new Set(
      originalNodes
        .filter(node => selectedPackages.has(node.group))
        .map(node => node.id)
    );

    let visibleIds = packageVisibleIds;
    if (term) {
      const matchingIds = new Set(
        originalNodes
          .filter(node => {
            if (!selectedPackages.has(node.group)) {
              return false;
            }
            const haystack = (String(node.label || "") + " " + String(node.title || "")).toLowerCase();
            return haystack.includes(term);
          })
          .map(node => node.id)
      );
      visibleIds = getReachableIds(matchingIds, selectedPackages);
    }

    nodes.update(originalNodes.map(node => ({
      id: node.id,
      hidden: !visibleIds.has(node.id)
    })));

    edges.update(originalEdges.map(edge => {
      const keepVisible =
        visibleIds.has(edge.from) &&
        visibleIds.has(edge.to);
      return {
        id: edge.id,
        hidden: !keepVisible
      };
    }));
  }

  input.addEventListener("input", applyFilters);
  packageCheckboxes.forEach(checkbox => checkbox.addEventListener("change", applyFilters));
  applyFilters();
});
</script>
"""
    return html_output.replace("<body>", "<body>\n" + injection, 1)


def write_outputs(class_map: dict[str, ClassInfo], graph: nx.DiGraph) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    positions = compute_positions(graph)
    module_graph = build_module_graph(graph)

    OUTPUT_JSON.write_text(
        json.dumps(build_json_payload(class_map, graph, positions, module_graph), indent=2),
        encoding="utf-8",
    )
    OUTPUT_SVG.write_text(render_svg(graph, positions), encoding="utf-8")
    OUTPUT_HTML.write_text(render_pyvis_html(graph, positions), encoding="utf-8")
    write_dot(graph)
    if LEGACY_OUTPUT_MD.exists():
        LEGACY_OUTPUT_MD.unlink()


def main() -> None:
    files = iter_project_files()
    class_index = build_class_index(files)
    class_map = build_class_map(files, class_index)
    graph = build_graph(class_map)
    write_outputs(class_map, graph)
    print(f"HTML scritto in: {OUTPUT_HTML.relative_to(ROOT)}")
    print(f"SVG scritto in: {OUTPUT_SVG.relative_to(ROOT)}")
    print(f"DOT scritto in: {OUTPUT_DOT.relative_to(ROOT)}")
    print(f"JSON scritto in: {OUTPUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
