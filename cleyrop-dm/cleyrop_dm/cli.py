"""Command-line interface: ``cleyrop-dm``.

    cleyrop-dm --project examples/retail plan   --env dev
    cleyrop-dm --project examples/retail apply  --env dev
    cleyrop-dm --project examples/retail run    --env prod --select customer_orders
    cleyrop-dm --project examples/retail promote --from dev --to prod
    cleyrop-dm --project examples/retail ls
    cleyrop-dm --project examples/retail history --model customer_orders
"""

from __future__ import annotations

import argparse
import sys

from cleyrop_dm.config import ProjectConfig
from cleyrop_dm.dag import Dag
from cleyrop_dm.model import load_models
from cleyrop_dm.runner import Runner


def _runner(args) -> Runner:
    return Runner(ProjectConfig.load(args.project))


def _select(args) -> set[str] | None:
    return set(args.select) if getattr(args, "select", None) else None


def cmd_ls(args) -> int:
    # `ls` only needs the parsed models/DAG, not a live catalog connection.
    project = ProjectConfig.load(args.project)
    models = load_models(project)
    dag = Dag(models, project)
    print(f"Project: {project.name}  (engine={project.engine}, ns={project.namespace})")
    for name in dag.topo_order():
        m = models[name]
        deps = ", ".join(sorted(dag.upstream(name))) or "-"
        audits = f"  audits: {len(m.config.audits)}" if m.config.audits else ""
        print(f"  {name:<26} {m.materialization.value:<12} deps: {deps}{audits}")
    return 0


def cmd_plan(args) -> int:
    r = _runner(args)
    plan = r.plan(args.env, _select(args))
    print(plan.describe())
    r.close()
    return 0


def cmd_apply(args) -> int:
    r = _runner(args)
    plan = r.plan(args.env, _select(args))
    print(plan.describe())
    if plan.has_changes:
        result = r.apply(plan)
        print(f"\nApplied to '{args.env}':")
        for m in result.materialized:
            tag = "created" if m.created else ("wap" if m.used_wap else "updated")
            print(f"  ✓ {m.model:<26} {m.rows:>6} rows  branch={m.branch}  [{tag}]")
        for s in result.skipped:
            print(f"  · {s:<26} (view, not materialised)")
    r.close()
    return 0


def cmd_run(args) -> int:
    return cmd_apply(args)


def cmd_promote(args) -> int:
    r = _runner(args)
    r.promote(args.from_env, args.to_env, _select(args))
    print(f"Promoted {', '.join(_select(args)) if _select(args) else 'all models'} "
          f"from '{args.from_env}' to '{args.to_env}'")
    r.close()
    return 0


def cmd_history(args) -> int:
    r = _runner(args)
    for h in r.catalog.history(args.model):
        print(f"  snapshot={h['snapshot_id']}  op={h['operation']}  ts={h['timestamp_ms']}")
    r.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cleyrop-dm", description="Manage Cleyrop Iceberg datasets.")
    p.add_argument("--project", required=True, help="Path to the project directory")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ls", help="List models and dependencies").set_defaults(func=cmd_ls)

    for name, func in (("plan", cmd_plan), ("apply", cmd_apply), ("run", cmd_run)):
        sp = sub.add_parser(name, help=f"{name} models")
        sp.add_argument("--env", default="prod")
        sp.add_argument("--select", nargs="*", help="Restrict to these models (+ ancestors)")
        sp.set_defaults(func=func)

    sp = sub.add_parser("promote", help="Blue/green promote one env onto another")
    sp.add_argument("--from", dest="from_env", required=True)
    sp.add_argument("--to", dest="to_env", required=True)
    sp.add_argument("--select", nargs="*")
    sp.set_defaults(func=cmd_promote)

    sp = sub.add_parser("history", help="Show Iceberg snapshot history for a model")
    sp.add_argument("--model", required=True)
    sp.set_defaults(func=cmd_history)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
