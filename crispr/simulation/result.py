from dataclasses import dataclass, fields, field
from typing import Dict, Optional, Any
from .setting import SimSetting


@dataclass
class Result:
    num_total_events: int
    final_events_per_sec: float
    setting: Optional[SimSetting] = None
    user_time: float = -1.0
    sys_time: float = -1.0
    real_time: float = -1.0
    error_message: str = ""
    sim_name: str = ""
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "num_total_events": self.num_total_events,
            "final_events_per_sec": self.final_events_per_sec,
            "sys": self.sys_time,
            "user": self.user_time,
            "real": self.real_time,
            "error": self.error_message,
            "sim_name": self.sim_name,
            **self.params,
        }

    @staticmethod
    def from_dict(d: Dict) -> "Result":
        result_fields = fields(Result)
        params = dict([(key, d[key]) for key in d if key not in result_fields])
        return Result(
            num_total_events=d["num_total_events"],
            final_events_per_sec=d["final_events_per_sec"],
            user_time=d["user"],
            sys_time=d["sys"],
            real_time=d["real"],
            error_message=d["error"],
            sim_name=d["sim_name"],
            params=params,
        )

    def to_log_str(self) -> str:
        return f"{self.sim_name} {self.num_total_events} events, {self.final_events_per_sec} ev/s"
