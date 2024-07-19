#!/usr/bin/env python
# -*- coding: utf-8 -*-


import datetime as dt
import unittest
from pathlib import Path

import log_analyzer


class TestConfigParsing(unittest.TestCase):
    sample_path: str = "./tests/"
    test_file_name: list[str] = ["nginx-access-ui.log-20180630"]

    def test_config_parsing_bad_path(self) -> None:
        test_path: str = "gibberish"
        with self.assertRaises(ValueError):
            log_analyzer.get_last_logfile_inf(test_path)

    def test_report_existence_check_bad_path(self) -> None:
        test_path = Path("/wrong/path")
        date = dt.date(2024, 4, 11)
        with self.assertRaises(ValueError):
            log_analyzer.report_already_exists(test_path, date)

    def test_log_file_existence_check_from_sample(self) -> None:
        full_path: log_analyzer.LogfileInf = log_analyzer.select_last_logfile(
            self.test_file_name
        )
        self.assertEqual(full_path.path, "nginx-access-ui.log-20180630")


class BaseLogAnalyzerTestCase(unittest.TestCase):
    @classmethod
    def setup(cls) -> None:
        cls.config = {
            "REPORT_SIZE": 1000,
            "REPORT_DIR": "./test/reports",
            "LOG_DIR": "./test/log",
        }


class ParseLogfileTest(BaseLogAnalyzerTestCase):
    def setUp(self) -> None:
        self.correct_line: str = (
            "1.196.116.32 -  - [02/Nov/2022:03:50:22 +0300] "
            '"GET /api/v2/banner/25019354 HTTP/1.1" 200 927 "-" '
            '"Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5" '
            '"-" "1496327422-2190076493-4743-9819059" "dc7161bv4" 0.390\n'
        )
        self.info_expected = log_analyzer.LogfileLineInfo(
            remote_addr="1.196.116.32",
            remote_user="-",
            http_x_real_ip="-",
            time_local="02/Nov/2022:03:50:22 +0300",
            request="GET /api/v2/banner/25019354 HTTP/1.1",
            URL="/api/v2/banner/25019354",
            status=200,
            body_bytes_sent=927,
            http_referer="-",
            http_user_agent="Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5",
            http_x_forwarded_for="-",
            http_X_REQUEST_ID="1496327422-2190076493-4743-9819059",
            http_X_RB_USER="dc7161bv4",
            request_time=0.390,
        )
        self.wrong: str = (
            "1.196.117.32 -  - [29/Jun/2019:03:50:22 +0300] "
            '"GET /api/v2/banner/25019354 HTTP/1.1" 200 927 "-" '
            '"Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5"'
            '"1498697422-23566854564-4743-9752759" "dc7161bv4"'
        )

    def test_parse_correct(self) -> None:
        info = log_analyzer.parse_logfile_line(self.correct_line)
        self.assertIsInstance(info, log_analyzer.LogfileLineInfo)
        self.assertEqual(info, self.info_expected)

    def test_parse_wrong(self) -> None:
        with self.assertRaises(expected_exception=ValueError):
            log_analyzer.parse_logfile_line(self.wrong)


if __name__ == "__main__":
    unittest.main()
