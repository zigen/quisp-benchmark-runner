import os, sys, asyncio
import click
from typing import List

from quisp_run.simulation import SimContext, SimSetting
from quisp_run.workers import Executor, Writer, job_display
from quisp_run.config import parse_config

from quisp_run.utils import console


@click.command()
@click.option(
    "--ui",
    "-u",
    default="Cmdenv",
    help="choose the UI to use: Cmdenv (default), Qtenv, Tkenv",
)
@click.option(
    "--ned-path",
    "-n",
    default="./modules:./channels:./networks",
    help="colon separated path list to NED files",
)
@click.option(
    "--config-file", "-c", default="./benchmark.ini", help="configuration file to use"
)
@click.option(
    "--sim-name",
    "-s",
    default=None,
    help="configuration name to run",
)
@click.option("--quisp-root", "-r", default="../quisp", help="QuISP root directory")
@click.option(
    "--dryrun",
    "-d",
    is_flag=True,
    default=False,
    help="dry run, show the command without running QuISP",
)
def run(ui, ned_path, config_file, sim_name, quisp_root, dryrun):
    if not os.path.exists(quisp_root):
        print(f"quisp_root: {quisp_root} not found", file=sys.stderr)
        exit(1)

    quisp_workdir = os.path.join(quisp_root, "quisp")
    exe_path = "./quisp"

    if not os.path.exists(os.path.join(quisp_root, exe_path)):
        print(f"quisp executable not found", file=sys.stderr)
        exit(1)

    config_file = os.path.abspath(os.path.join(os.getcwd(), config_file))

    # add config dir to ned path
    ned_path += ":" + os.path.abspath(os.path.join(os.getcwd(), "config/topology"))

    asyncio.run(
        start_simulations(
            exe_path, ui, config_file, sim_name, ned_path, [], dryrun, quisp_workdir
        )
    )


async def start_simulations(
    exe_path, ui, config_file, sim_name, ned_path, opts, dryrun, quisp_workdir
):
    # if dryrun:
    #     print(cmd.to_str())
    #     exit(0)

    console.print(f"Working dir: {quisp_workdir}")
    pool_size = 8
    sim_settings: List[SimSetting] = []

    with open("simulation.plan", "r") as f:
        source = f.read()
        plan = parse_config(source)
        sim_settings = plan.populate()

    sim_context = SimContext(
        exe_path, ui, ned_path, quisp_workdir, pool_size, sim_settings
    )

    workers = [Executor(i, sim_context) for i in range(pool_size)]
    worker_tasks = [asyncio.create_task(worker.run()) for worker in workers]
    display_task = asyncio.create_task(job_display(workers, sim_context, console))
    writer = Writer(sim_context)
    writer_task = asyncio.create_task(writer.run())
    await asyncio.gather(display_task, writer_task, *worker_tasks)