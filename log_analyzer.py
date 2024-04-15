#!/usr/bin/env python
# -*- coding: utf-8 -*-


# log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';

import argparse
import datetime
import gzip
import json
import logging
import os
import re
import string
import sys
from collections import defaultdict, namedtuple
from enum import Enum
from pathlib import Path
from statistics import median
from typing import Callable, Dict, Iterator, List, Optional

config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log",
}

logging_filename = config.get("LOGGING_FILENAME")
logging.basicConfig(
    format="[%(asctime)s] %(levelname).1s %(message)s",
    datefmt="%Y.%m.%d %H:%M:%S",
    filename=logging_filename,
    level="INFO",
)

TEMPLATE_PATH = Path("./template/report.html").resolve()
ERROR_THRESHOLD = 0.2


class LogfileType(Enum):
    PLAIN = ""
    GZIP = "gz"


LogfileInfo = namedtuple("LogfileInfo", ["path", "date", "type"])


LogfileLineInfo = namedtuple(
    "LogfileLineInfo",
    [
        "remote_addr",
        "remote_user",
        "http_x_real_ip",
        "time_local",
        "request",
        "URL",
        "status",
        "body_bytes_sent",
        "http_referer",
        "http_user_agent",
        "http_x_forwarded_for",
        "http_X_REQUEST_ID",
        "http_X_RB_USER",
        "request_time",
    ],
)


URLStats = namedtuple(
    "URLStats",
    [
        "url",
        "count",
        "count_perc",
        "time_sum",
        "time_perc",
        "time_avg",
        "time_max",
        "time_med",
    ],
)

logfile_line_pattern = (
    r"^([\S]+)\s+"
    + r"([\S]+)\s+"
    + r"([\S]+)\s+"
    + r"\[(.*?)\]\s+"
    + r"\"([A-Z]+\s+(\S+)\s+.*?)\"\s+"
    + r"(\d{3})\s+"
    + r"(\d+)\s+"
    + r"\"(.*?)\"\s+"
    + r"\"(.*?)\"\s+"
    + r"\"(.*?)\"\s+"
    + r"\"(.*?)\"\s+"
    + r"\"(.*?)\"\s+"
    + r"(\d+\.?\d*)"
)

logfile_line_patter_obj: re.Pattern = re.compile(logfile_line_pattern)


def get_last_logfile_info(log_dir: str | Path) -> Optional[LogfileInfo]:
    log_path = Path(log_dir).resolve()
    if not log_path.is_dir():
        err_msg = f"incorrect log dir: '{log_dir}'"
        logging.error(err_msg)
        raise ValueError(err_msg)

    files = [i.name for i in log_path.iterdir() if i.is_file()]
    info = select_last_logfile(files=files)
    return info._replace(path=log_path.joinpath(info.path)) if info else None


def select_last_logfile(files: List[str]) -> Optional[LogfileInfo]:
    filename_pattern = r"^nginx-access-ui.log-(19\d\d|20\d\d)([01]\d)([0-3]\d)(\.gz|)$"
    pattern_obj = re.compile(pattern=filename_pattern)

    result = LogfileInfo(path=None, date=datetime.date.min, type=None)
    today = datetime.date.today()
    for entry in files:
        match = pattern_obj.match(entry)

        try:
            cur_date = datetime.date(
                year=int(match.group(1)),
                month=int(match.group(2)),
                day=int(match.group(3)),
            )
        except Exception:
            logging.exception("unable to create a date from %s object", match)
            continue

        if cur_date > result.date:
            result = LogfileInfo(
                path=entry,
                date=cur_date,
                type=LogfileType.PLAIN
                if len(match.group(4)) == 0
                else LogfileType.GZIP,
            )

            if cur_date == today:
                break

    if result.path is not None:
        return result
    return


def parse_logfile_line(line: str) -> LogfileLineInfo:
    m: re.Match[str] | None = re.match(logfile_line_patter_obj, line)
    if m is None:
        raise ValueError("incorrect line structure")
    info: LogfileLineInfo = LogfileLineInfo._make(m.group(*range(1, 15)))
    info = info._replace(
        status=int(info.status),
        body_bytes_sent=int(info.body_bytes_sent),
        request_time=float(info.request_time),
    )
    return info


def parse_logfile(
    logfile_info: LogfileInfo,
    logfile_line_parser: Callable[[str], LogfileLineInfo] = parse_logfile_line,
) -> Iterator[Optional[LogfileLineInfo]]:
    if not os.path.isfile(logfile_info.path):
        raise ValueError(f"incorrect logfile path: '{logfile_info.path}'")

    with open(
        logfile_info.path, "rb"
    ) if logfile_info.type is LogfileType.PLAIN else gzip.open(
        logfile_info.path, "r"
    ) as fd:
        for line_binary in fd:
            line = str(line_binary, encoding="utf-8")
            try:
                yield logfile_line_parser(line)
            except ValueError:
                logging.warning("unable to parse a line:\n'%s'", line)
                yield


def get_logfile_stats(
    logfile_info: LogfileInfo,
    logfile_parser: Callable[[LogfileInfo], Iterator[Optional[LogfileLineInfo]]],
    result_size: int,
) -> List[URLStats]:
    stats = dict()
    total_lines = 0
    err_lines = 0
    summary_time = 0.0
    req_times = defaultdict(list)

    info: LogfileLineInfo
    for info in logfile_parser(logfile_info):
        total_lines += 1
        if info is None:
            err_lines += 1
            continue
        if stats.get(info.URL) is None:
            stats[info.URL] = URLStats(
                count=1,
                time_avg=0.0,
                time_max=info.request_time,
                time_sum=info.request_time,
                url=info.URL,
                time_med=0.0,
                time_perc=0.0,
                count_perc=0.0,
            )

        else:
            stats[info.URL] = stats[info.URL]._replace(
                count=stats[info.URL].count + 1,
                time_sum=float(
                    format(stats[info.URL].time_sum + info.request_time, ".3f")
                ),
                time_max=max(stats[info.URL].time_max, info.request_time),
            )
        summary_time += info.request_time
        req_times[info.URL].append(info.request_time)

    err_perc = err_lines / total_lines
    if err_perc > ERROR_THRESHOLD:
        logging.error(
            "error threshold = %.2f exceeded, current error rate is %.2f",
            ERROR_THRESHOLD,
            err_perc,
        )
        raise RuntimeError("parsing error threshold exceeded")

    result: List[URLStats] = sorted(
        list(stats.values()), key=lambda x: x.time_sum, reverse=True
    )[:result_size]
    for idx, elem in enumerate(result):
        result[idx] = elem._replace(
            count_perc=f"{elem.count / (total_lines - err_lines) * 100.0:.3f}",
            time_perc=f"{elem.time_sum / summary_time * 100.0:.3f}",
            time_avg=f"{elem.time_sum / elem.count:.3f}",
            time_med=f"{median(req_times[elem.url]):.3f}",
        )

    return result


def report_date(date: datetime.date) -> str:
    return f"report-{date.strftime("%Y.%m.%d")}.html"


def report_already_exists(report_path: Path, date: datetime.date) -> bool:
    if not report_path.is_dir():
        raise ValueError(f"incorrect report dir: '{report_path}'")
    return report_path.joinpath(report_date(date)).is_file()


def render_template(table_json: List[Dict], report_path: Path) -> None:
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as tf:
        s = string.Template(tf.read()).safe_substitute(table_json=table_json)
    with open(report_path, "w", encoding="utf-8") as of:
        of.write(s)


def parse_config(config_text: str) -> Dict[str, str]:
    file_config = dict()

    if len(config_text) > 0:
        file_config = json.loads(config_text)

    return file_config


def config_setup(config: Dict) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default=config,
        help="path to a configuration file",
    )

    try:
        args = parser.parse_args()
        config_file = args.config

        if isinstance(config_file, str):
            config_text = ""
            with open(config_file, "r") as text:
                config_text = text.read()

            file_config = parse_config(config_text)
        else:
            file_config = config_file
    except Exception:
        logging.exception("unable to parse a configuration file")
        return

    config.update(**file_config)


def main(config: Dict) -> None:
    config_setup(config)

    report_path = Path(config.get("REPORT_DIR"))

    try:
        last_logfile_info = get_last_logfile_info(log_dir=config.get("LOG_DIR"))

        if last_logfile_info is None:
            logging.info("logfiles were not found in '%s'", config.get("LOG_DIR"))
            return

        logging.info("last logfile found: %s", last_logfile_info.path)

        if report_already_exists(report_path=report_path, date=last_logfile_info.date):
            logging.info(
                "Report for '%s' has already been created in '%s'",
                last_logfile_info.path,
                report_path,
            )
            return

        table_json = [
            dict(stats._asdict())
            for stats in get_logfile_stats(
                logfile_info=last_logfile_info,
                logfile_parser=parse_logfile,
                result_size=config.get("REPORT_SIZE"),
            )
        ]

        new_report_path = report_path.joinpath(report_date(date=last_logfile_info.date))
        render_template(table_json=table_json, report_path=new_report_path)
    except Exception:
        logging.exception("unable to finish a task")
        sys.exit(1)


if __name__ == "__main__":
    main(config)
