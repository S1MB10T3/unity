# Open Assistant 0.21
# 2018 General Public License V3
# By Alex Kamosko, Andrew Vavrek, Jenya Chernotalova

# oa.py - Launch Open Assistant.

import os, time
import importlib
import logging
import signal
import threading

from core import oa, queue, Core




class OpenAssistant:
    """ Main OA loading class. """
    
    def __init__(self):
        logging.info("Initializing Open Assistant")

        # Establish OA core.
        oa.core = self
        oa.core_directory = os.path.dirname(__file__)

        # Activate OA.
        self.finished = threading.Event()
    
        # Setup parts and threads.
        oa.core.parts = Core()
        oa.core.minds = Core()
        oa.core.mind = None
        self.thread_pool = []


    def run(self):
        """ Remain active until exit. """
        self.load_modules()
        self.start_modules()

        # Setup connections between parts.
        # XXX: can't ensure load order yet
        oa.core.parts.ear.output += [oa.core.parts.speech_recognition]
        oa.core.parts.speech_recognition.output += [oa.core.parts.mind]
        # oa.core.parts.keyboard.output = [oa.mind, oa.display]
        # oa.core.parts.mind.output = [oa.display]

        self.finished.wait()


    def load_modules(self):
        """ Setup all parts. """

        pkg = os.path.split(oa.core_directory)[-1]

        logging.info("Loading Modules..")
        for module_name in os.listdir(os.path.join(oa.core_directory, 'modules')):
            try:

                # A module is a folder with an __oa__.py file
                if not all([
                    os.path.isdir(os.path.join('modules', module_name)),
                    os.path.exists(os.path.join('modules', module_name, '__oa__.py')),
                ]): continue

                # Import part as module
                logging.info('{} <- {}'.format(module_name, os.path.abspath(os.path.join('modules', module_name))))
                M = importlib.import_module('modules.{}'.format(module_name), package=pkg)

                # If the module provides an input queue, link it
                if getattr(M, '_in', None) is not None:

                    m = Core()
                    m.name = module_name

                    m.__dict__.setdefault('wire_in', queue.Queue())
                    m.__dict__.setdefault('output', [])

                    m.__dict__.update(M.__dict__)
                    
                    oa.core.parts[module_name] = m
                    
            except Exception as ex:
                logging.error(ex)


    def start_modules(self):
        # Setup input threads.
        for module_name in oa.core.parts:
            m = oa.core.parts[module_name]
            if getattr(m, '_in', None) is not None:
                thr = threading.Thread(target=thread_loop, name=module_name, args=(m,))
                self.thread_pool.append(thr)

        # Start all threads.
        [thr.start() for thr in self.thread_pool]


def thread_loop(part):
    """ Setup part inputs to the message wire. """
    if not isinstance(part.output, list):
        raise Exception('No output list defined: ' + part.name)

    if hasattr(part, 'init'):
        part.init()

    logging.debug('Started')

    muted = False
    try:
        for message in part._in():
            if not muted:
                for listener in part.output:
                    try:
                        logging.debug('{} -> {}'.format(part.name, listener.name))
                        listener.wire_in.put(message)
                    except Exception as ex:
                        logging.error("Sending {} -> {}: {}".format(part.name, listener.name, ex))
    except Exception as ex:
        logging.error(ex)

    logging.debug('Stopped')


""" Boot Open Assistant. """
def runapp():
    try:
        a = OpenAssistant()
        a.run()

    except KeyboardInterrupt:
        logging.info("Ctrl-C Pressed")

        logging.info("Signaling Shutdown")
        oa.core.finished.set()
        
        logging.info('Waiting on threads')
        [thr.join() for thr in oa.core.thread_pool]
        logging.info('Threads closed')


if __name__ == '__main__':
    # filename='oa.log'
    logging.basicConfig(level=logging.DEBUG, format="[%(asctime)s] %(levelname)-8s %(threadName)-24s [%(filename)s:%(funcName)s:%(lineno)d]\t  %(message)s")
    logging.info("Open Assistant Starting..")

    runapp()
    quit(0)
