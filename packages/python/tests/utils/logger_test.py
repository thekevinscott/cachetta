"""Unit tests for cachetta.utils.logger."""

import logging

from cachetta.utils.logger import logger


def describe_logger():
    def test_logger_is_a_standard_logging_logger():
        assert isinstance(logger, logging.Logger)

    def test_logger_is_named_cachetta():
        assert logger.name == "cachetta"
