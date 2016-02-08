import logging

logger = logging.getLogger('harrier')
logger.propagate = False
stream = logging.StreamHandler()
formatter = logging.Formatter('%(levelname)-7s - %(message)s ')
stream.setFormatter(formatter)
logger.addHandler(stream)
logger.setLevel(logging.INFO)


class HarrierKnownProblem(Exception):
    pass

