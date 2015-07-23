__author__ = 'alexandermarquardt'

import datetime
import hashlib
import hmac
import logging
import time

from base64 import b64encode

from video_src import constants
from video_src import http_helpers
from video_src.error_handling import handle_exceptions
from request_handler_custom.base_handler import BaseHandlerClientVerified

shared_secret = 'foobarBAM33ttXXvv99poo'
turn_ip = '130.211.82.191'
turn_uri_combinations = [('3478', 'udp'), ('3478', 'tcp'), ('3479', 'udp'), ('3479', 'tcp')]


class TurnRestCredentials(BaseHandlerClientVerified):

    @handle_exceptions
    def post(self):
        client_id = self.session.client_obj.key.id()

        expire_dt = datetime.datetime.utcnow() + datetime.timedelta(minutes=constants.turn_relay_timeout_minutes)
        expire_ts = int(time.mktime((expire_dt).timetuple()))

        expire_datetime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expire_ts))
        logging.debug('turn rest expires at %s (epoch value %d)' % (expire_datetime, expire_ts))

        uris = []
        for option in turn_uri_combinations:
            uris.append("turn:%s:%s?transport=%s" % (turn_ip, option[0], option[1]))

        turn_username = "%d:%s" % (expire_ts, client_id)
        turn_password = b64encode(hmac.new(shared_secret, turn_username, hashlib.sha1).digest())

        response_dict = {
            'turn_username': turn_username,
            'turn_password': turn_password,
            'uris': uris
        }

        http_helpers.set_http_ok_json_response(self.response, response_dict)