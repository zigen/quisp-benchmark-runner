import asyncio
import re
from rich.progress import TaskID
from command import Command
from typing import List, Optional
from enum import Enum


class WorkerStatus(Enum):
    WAINTING_FOR_TASK = "Waiting for task"
    STARTING = "Starting"
    RUNNING = "Running"
    FINISHING = "Finishing"
    FINISHED = "Finished"
    STOPPED = "Stopped"
    ERROR = "Error"


class Worker:
    id: int
    task_id: Optional[TaskID]
    lock: asyncio.Lock
    num_events: int
    ev_per_sec: int
    sim_name: str
    sim_changed: bool
    status: WorkerStatus

    def __init__(self, id: int):
        self.id = id
        self.task_id = None
        self.lock = asyncio.Lock()
        self.num_events = 0
        self.ev_per_sec = 0
        self.sim_name = ""
        self.sim_changed = False
        self.status = WorkerStatus.WAINTING_FOR_TASK

    async def run(
        self,
        tasks: asyncio.Queue[Optional[Command]],
        results: asyncio.Queue,
        workdir: str,
    ):
        await self.set_status(WorkerStatus.WAINTING_FOR_TASK)
        while True:
            cmd: Optional[Command] = await tasks.get()
            if cmd is None:
                await self.set_status(WorkerStatus.STOPPED)
                break

            await self.init_with_new_task(cmd)
            await self.run_quisp(cmd.to_list(), workdir=workdir)
            await results.put(cmd)

    async def set_status(self, status: WorkerStatus):
        async with self.lock:
            self.status = status

    async def init_with_new_task(self, cmd: Command):
        async with self.lock:
            self.sim_name = cmd.config_name + str(cmd.opts)
            self.num_events = 0
            self.ev_per_sec = 0
            self.sim_changed = True
            self.status = WorkerStatus.STARTING

    async def run_quisp(self, cmd: List[str], workdir: str = "./"):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
        )
        if proc.stdout is None or proc.stderr is None:
            return
        stdout = proc.stdout
        stderr = proc.stderr
        running = False  # whether quisp's initializing phase is finished or not
        while True:
            if stdout.at_eof() and stderr.at_eof():
                break
            lines = []

            # stdout example:
            # ** Event #1225984   t=10.000104015903   Elapsed: 96.8616s (1m 36s)  76% completed  (76% total)
            #     Speed:     ev/sec=9170.57   simsec/sec=9.70194e-08   ev/simsec=9.45231e+10
            #     Messages:  created: 3759524   present: 15381   in FES: 9122

            while len(stdout._buffer) > 0:  # type: ignore
                buf = (await proc.stdout.readline()).decode().strip()
                if not buf:
                    break
                if buf.startswith("<!> Error"):
                    await self.set_status(WorkerStatus.ERROR)
                if buf.startswith("End."):
                    running = False
                    await self.set_status(WorkerStatus.FINISHING)

                if buf.startswith("** Event"):
                    if not running:
                        running = True
                        await self.set_status(WorkerStatus.RUNNING)
                    match = re.search("Event #(\d+)", buf)
                    if match:
                        async with self.lock:
                            self.num_events = int(match.group(1))
                if buf.startswith("Speed:"):
                    match = re.search(
                        "ev/sec=([0-9.]+)\s+simsec/sec=([0-9.\-\+e]+)\s+ev/simsec=([0-9.\-\+e]+)",
                        buf,
                    )
                    if match:
                        async with self.lock:
                            self.ev_per_sec = int(match.group(1))
                    lines.append(re.sub("\s+", ",", buf))
            while len(stderr._buffer) > 0:  # type: ignore
                buf = (await proc.stderr.readline()).decode().strip()
                print("Err: ", buf)
            await asyncio.sleep(1)
        await proc.communicate()
        await self.set_status(WorkerStatus.FINISHED)
