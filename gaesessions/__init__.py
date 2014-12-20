"""A fast, lightweight, and secure session WSGI middleware for use with GAE."""
from Cookie import CookieError, SimpleCookie
from base64 import b64decode, b64encode
import binascii
import datetime
import hashlib
import hmac
import logging
import pickle
import os
import time
import webapp2

from google.appengine.ext import ndb
from google.appengine.api import taskqueue
from google.appengine.api.datastore import entity_pb

from video_src import status_reporting

# ARM Note: We do not allow cookie-only session so that if we need to eliminate a user from the system and immediately
# revoke their website access, this can be achieved by just removing their session from the datastore.
# This should be revisited in the future to see if there are other methods of achieving this functionality
# while using cookie-only sessions, as cookie-only sessions would likely be better since we are passing a small
# amount of data between the client and the server.

# Configurable cookie options
COOKIE_NAME_PREFIX = "lx-session-"  # identifies a cookie as being one used by gae-sessions (so you can set cookies too)
COOKIE_PATH = "/"
# Original DEFAULT_COOKIE_ONLY_THRESH was 10240 10KB: GAE only allows ~16000B in HTTP header - leave ~6KB for other info
# However, we set to 0 because we don't want cookie-only sessions - we need to be able to remotely kills sessions 
# which requires that all sessions are in the database.
DEFAULT_COOKIE_ONLY_THRESH = 0 
DEFAULT_LIFETIME = datetime.timedelta(hours=24)

# constants
SID_LEN = 43  # timestamp (10 chars) + underscore + urandom (32 hex chars)
SIG_LEN = 44  # base 64 encoded HMAC-SHA256
MAX_COOKIE_LEN = 4096
EXPIRE_COOKIE_FMT = ' %s=; expires=Wed, 01-Jan-1970 00:00:00 GMT; Path=' + COOKIE_PATH
COOKIE_FMT = ' ' + COOKIE_NAME_PREFIX + '%02d="%s"; %sPath=' + COOKIE_PATH + '; HttpOnly'
COOKIE_FMT_SECURE = COOKIE_FMT + '; Secure'
COOKIE_DATE_FMT = '%a, %d-%b-%Y %H:%M:%S GMT'
COOKIE_OVERHEAD = len(COOKIE_FMT % (0, '', '')) + len('expires=Xxx, xx XXX XXXX XX:XX:XX GMT; ') + 150  # 150=safety margin (e.g., in case browser uses 4000 instead of 4096)
MAX_DATA_PER_COOKIE = MAX_COOKIE_LEN - COOKIE_OVERHEAD


def is_gaesessions_key(k):
    return k.startswith(COOKIE_NAME_PREFIX)


class SessionModel(ndb.Model):
    """Contains session data.  id is the session ID and pdump contains a
    pickled dictionary which maps session variables to their values."""
    pdump = ndb.BlobProperty()


class Session(object):
    """Manages loading, reading/writing key-value pairs, and saving of a session.

    ``sid`` - if set, then the session for that sid (if any) is loaded. Otherwise,
    sid will be loaded from the HTTP_COOKIE (if any).
    """
    DIRTY_BUT_DONT_PERSIST_TO_DB = 0

    def __init__(self, sid=None, lifetime=DEFAULT_LIFETIME,
                 cookie_only_threshold=DEFAULT_COOKIE_ONLY_THRESH, cookie_key=None):
        self._accessed = False
        self.sid = None
        self.cookie_keys = []
        self.cookie_data = None
        self.data = {}
        self.dirty = False  # has the session been changed?

        self.lifetime = lifetime
        self.cookie_only_thresh = cookie_only_threshold
        self.base_key = cookie_key

        if sid:
            self.__set_sid(sid, False)
            self.data = None
        else:
            self.__read_cookie()

    @staticmethod
    def __compute_hmac(base_key, sid, text):
        """Computes the signature for text given base_key and sid."""
        key = base_key + sid
        return b64encode(hmac.new(key, text, hashlib.sha256).digest())

    def __read_cookie(self):
        """Reads the HTTP Cookie and loads the sid and data from it (if any)."""
        try:
            # check the cookie to see if a session has been started
            cookie = SimpleCookie(os.environ['HTTP_COOKIE'])
            self.cookie_keys = filter(is_gaesessions_key, cookie.keys())
            if not self.cookie_keys:
                return  # no session yet
            self.cookie_keys.sort()
            data = ''.join(cookie[k].value for k in self.cookie_keys)
            i = SIG_LEN + SID_LEN
            sig, sid, b64pdump = data[:SIG_LEN], data[SIG_LEN:i], data[i:]
            pdump = b64decode(b64pdump)
            actual_sig = Session.__compute_hmac(self.base_key, sid, pdump)
            if sig == actual_sig:
                self.__set_sid(sid, False)
                # check for expiration and terminate the session if it has expired
                if self.get_expiration() != 0 and time.time() > self.get_expiration():
                    return self.terminate()

                if pdump:
                    self.data = self.__decode_data(pdump)
                else:
                    self.data = None  # data is in db: load it on-demand
            else:
                logging.warn('cookie with invalid sig received from %s: %s' % (os.environ.get('REMOTE_ADDR'), b64pdump))
        except (CookieError, KeyError, IndexError, TypeError):
            # there is no cookie (i.e., no session) or the cookie is invalid
            self.terminate(False)

    def make_cookie_headers(self):
        """Returns a list of cookie headers to send (if any)."""
        # expire all cookies if the session has ended
        if not self.sid:
            return [EXPIRE_COOKIE_FMT % k for k in self.cookie_keys]

        if self.cookie_data is None:
            return []  # no cookie headers need to be sent

        # build the cookie header(s): includes sig, sid, and cookie_data
        if self.is_ssl_only():
            m = MAX_DATA_PER_COOKIE - 8
            fmt = COOKIE_FMT_SECURE
        else:
            m = MAX_DATA_PER_COOKIE
            fmt = COOKIE_FMT
        sig = Session.__compute_hmac(self.base_key, self.sid, self.cookie_data)
        cv = sig + self.sid + b64encode(self.cookie_data)
        num_cookies = 1 + (len(cv) - 1) / m
        if self.get_expiration() > 0:
            ed = "expires=%s; " % datetime.datetime.fromtimestamp(self.get_expiration()).strftime(COOKIE_DATE_FMT)
        else:
            ed = ''
        cookies = [fmt % (i, cv[i * m:i * m + m], ed) for i in xrange(num_cookies)]

        # expire old cookies which aren't needed anymore
        old_cookies = xrange(num_cookies, len(self.cookie_keys))
        key = COOKIE_NAME_PREFIX + '%02d'
        cookies_to_ax = [EXPIRE_COOKIE_FMT % (key % i) for i in old_cookies]
        return cookies + cookies_to_ax

    def is_active(self):
        """Returns True if this session is active (i.e., it has been assigned a
        session ID and will be or has been persisted)."""
        return self.sid is not None

    def is_ssl_only(self):
        """Returns True if cookies set by this session will include the "Secure"
        attribute so that the client will only send them over a secure channel
        like SSL)."""
        return self.sid is not None and self.sid[-33] == 'S'

    def is_accessed(self):
        """Returns True if any value of this session has been accessed."""
        return self._accessed

    def ensure_data_loaded(self):
        """Fetch the session data if it hasn't been retrieved it yet."""
        self._accessed = True
        if self.data is None and self.sid:
            self.__retrieve_data()

    def get_expiration(self):
        """Returns the timestamp at which this session will expire."""
        try:
            return int(self.sid[:-33])
        except:
            return 0
        
    def get_expiration_datetime(self):
        expiry_timestamp = self.get_expiration()
        return datetime.datetime.fromtimestamp(expiry_timestamp)   
    
    def __make_sid(self, expire_ts=None, ssl_only=False):
        """Returns a new session ID."""
        # make a random ID (random.randrange() is 10x faster but less secure?)
        if expire_ts is None:
            expire_dt = datetime.datetime.now() + self.lifetime
            expire_ts = int(time.mktime((expire_dt).timetuple()))
        else:
            expire_ts = int(expire_ts)
        if ssl_only:
            sep = 'S'
        else:
            sep = '_'
        return ('%010d' % expire_ts) + sep + binascii.hexlify(os.urandom(16))

    @staticmethod
    def __encode_data(d):
        """Returns a "pickled+" encoding of d.  d values of type ndb.Model are
        protobuf encoded before pickling to minimize CPU usage & data size."""
        # separate protobufs so we'll know how to decode (they are just strings)
        eP = {}  # for models encoded as protobufs
        eO = {}  # for everything else
        for k, v in d.iteritems():
            if isinstance(v, ndb.Model):
                eP[k] = ndb.ModelAdapter().entity_to_pb(v).Encode()
            else:
                eO[k] = v
        return pickle.dumps((eP, eO), 2)

    @staticmethod
    def __decode_data(pdump):
        """Returns a data dictionary after decoding it from "pickled+" form."""
        try:
            eP, eO = pickle.loads(pdump)
            for k, v in eP.iteritems():
                eO[k] = ndb.ModelAdapter().pb_to_entity(entity_pb.EntityProto(v))
        except Exception, e:
            logging.warn("failed to decode session data: %s" % e)
            eO = {}
        return eO


    def regenerate_id(self, expiration_ts=None):
        """Assigns the session a new session ID (data carries over).  This
        should be called whenever a user authenticates to prevent session
        fixation attacks.

        ``expiration_ts`` - The UNIX timestamp the session will expire at. If
        omitted, the session expiration time will not be changed.
        """
        if self.sid or expiration_ts is not None:
            self.ensure_data_loaded()  # ensure we have the data before we delete it
            if expiration_ts is None:
                expiration_ts = self.get_expiration()
            self.__set_sid(self.__make_sid(expiration_ts, self.is_ssl_only()))
            self.dirty = True  # ensure the data is written to the new session

    def start(self, expiration_ts=None, ssl_only=False):
        """Starts a new session.  expiration specifies when it will expire.  If
        expiration is not specified, then self.lifetime will used to
        determine the expiration date.

        Normally this method does not need to be called directly - a session is
        automatically started when the first value is added to the session.

        ``expiration_ts`` - The UNIX timestamp the session will expire at. If
        omitted, the session will expire after the default ``lifetime`` has past
        (as specified in ``SessionMiddleware``).

        ``ssl_only`` - Whether to specify the "Secure" attribute on the cookie
        so that the client will ONLY transfer the cookie over a secure channel.
        """
        self.dirty = True
        self.data = {}
        self.__set_sid(self.__make_sid(expiration_ts, ssl_only), True)

    def terminate(self, clear_data=True):
        """Deletes the session and its data, and expires the user's cookie."""
        if clear_data:
            self.__clear_data()
        self.sid = None
        self.data = {}
        self.dirty = False
        if self.cookie_keys:
            self.cookie_data = ''  # trigger the cookies to expire
        else:
            self.cookie_data = None

    def __set_sid(self, sid, make_cookie=True):
        """Sets the session ID, deleting the old session if one existed.  The
        session's data will remain intact (only the session ID changes)."""
        if self.sid:
            self.__clear_data()
        self.sid = sid
        self.ndb_key = ndb.Key(SessionModel._get_kind(), sid, namespace='')

        # set the cookie if requested
        if make_cookie:
            self.cookie_data = ''  # trigger the cookie to be sent

    def __clear_data(self):
        """Deletes this session from the datastore."""
        logging.info("erasing session from database  %s" % self.sid)
        if self.sid:
            try:
                self.ndb_key.delete()
            except:
                pass  # it wasn't in the db (maybe cookie only or db is down) => cron will expire it

    def __retrieve_data(self):
        """Sets the data associated with this session after retrieving it from
        the datastore.  Assumes self.sid is set.  Checks for session
        expiration after getting the data."""

        session_model_instance = self.ndb_key.get()
        if session_model_instance:
            pdump = session_model_instance.pdump
        else:
            expiry_datetime = self.get_expiration_datetime()
            # This can happen if the user has multiple windows open, and logs out in one of the windows but
            # the other windows continue to request information.
            logging.warning("can't find session data in the datastore for sid=%s key = %s expiry: %s" % (self.sid, self.ndb_key, expiry_datetime))
            self.terminate(False)  # we lost it; just kill the session
            return

        self.data = self.__decode_data(pdump)

    def save(self, persist_even_if_using_cookie=True):
        """Saves the data associated with this session IF any changes have been
        made (specifically, if any mutator methods like __setitem__ or the like
        is called).

        If the data is small enough it will be sent back to the user in a cookie
        instead of using the datastore.  If `persist_even_if_using_cookie`
        evaluates to True, the datastore will also be used.

        Normally this method does not need to be called directly - a session is
        automatically saved at the end of the request if any changes were made.
        """
        if not self.sid:
            return  # no session is active
        if not self.dirty:
            return  # nothing has changed
        dirty = self.dirty
        self.dirty = False  # saving, so it won't be dirty anymore

        # do the pickling ourselves b/c we need it for the datastore anyway
        pdump = self.__encode_data(self.data)

        # Commented out by ARM - we do not allow cookie-only sessions, so don't waste resources computing
        # the length. 
        # persist via cookies if it is reasonably small
        #if len(pdump) * 4 / 3 <= self.cookie_only_thresh:  # 4/3 b/c base64 is ~33% bigger
            #self.cookie_data = pdump
            #if not persist_even_if_using_cookie:
                #return
        #elif self.cookie_keys:
            ## latest data will only be in the backend, so expire data cookies we set
            #self.cookie_data = ''
        if self.cookie_keys:
            # latest data will only be in the backend, so expire data cookies we set            
            self.cookie_data = ''


        # persist the session to the datastore            
        try:
            SessionModel(id=self.sid, pdump=pdump).put()
        except Exception, e:
            logging.error("unable to persist session to datastore for sid=%s (%s)" % (self.sid, e))

    # Users may interact with the session through a dictionary-like interface.
    def clear(self):
        """Removes all data from the session (but does not terminate it)."""
        if self.sid:
            self.data = {}
            self.dirty = True

    def get(self, key, default=None):
        """Retrieves a value from the session."""
        self.ensure_data_loaded()
        return self.data.get(key, default)

    def has_key(self, key):
        """Returns True if key is set."""
        self.ensure_data_loaded()
        return key in self.data

    def pop(self, key, default=None):
        """Removes key and returns its value, or default if key is not present."""
        self.ensure_data_loaded()
        self.dirty = True
        return self.data.pop(key, default)


    def __getitem__(self, key):
        """Returns the value associated with key on this session."""
        self.ensure_data_loaded()
        return self.data.__getitem__(key)

    def __setitem__(self, key, value):
        """Set a value named key on this session.  This will start a session if
        one is not already active."""
        self.ensure_data_loaded()
        if not self.sid:
            self.start()
        self.data.__setitem__(key, value)
        self.dirty = True

    def __delitem__(self, key):
        """Deletes the value associated with key on this session."""
        self.ensure_data_loaded()
        self.data.__delitem__(key)
        self.dirty = True

    def __iter__(self):
        """Returns an iterator over the keys (names) of the stored values."""
        self.ensure_data_loaded()
        return self.data.iterkeys()

    def __contains__(self, key):
        """Returns True if key is present on this session."""
        self.ensure_data_loaded()
        return self.data.__contains__(key)

    def __str__(self):
        """Returns a string representation of the session."""
        if self.sid:
            self.ensure_data_loaded()
            return "SID=%s %s" % (self.sid, self.data)
        else:
            return "uninitialized session"


class SessionAdmin(webapp2.RequestHandler):

    def delete_expired_sessions(self):
        """Deletes expired sessions from the datastore.
        If there are more than 500 expired sessions, only 500 will be removed.
        """
        now_str = unicode(int(time.time()))
        q = SessionModel.query()
        k = ndb.Key('SessionModel', now_str + u'\ufffd')
        q.filter(SessionModel._key < k)
        results = q.fetch(500, keys_only=True,)
        num_results = len(results)
        ndb.delete_multi([k for k in results])
        return num_results


    def cleanup_sessions(self):
        # wrapper for delete_expired_sessions that calls it multiple times if additional sessions need to be
        # removed.  (You must add the appropriate URL to urls.py as well as to the taskqueue.add function call
        # below for this to work correctly).

        try:
            num_cleaned_up = self.delete_expired_sessions
            msg = "gae-sessions:cleanup_sessions(): deleted %d expired sessions from the datastore" % num_cleaned_up
            logging.info(msg)
            if num_cleaned_up >= 500:
                # re-schedule to cleanup remaining sessions immideately, since we didn't get them all in the previous cleanup
                logging.info("Re-launching session cleanup since we did not get all in the previous")
                time.sleep(1.0) # just in case it takes a few milliseconds for the DB to get updated
                taskqueue.add(queue_name = 'cleanup-sessions-queue', url='/rs/admin/cleanup_sessions/')

            self.response.write("OK")
        except:
            status_reporting.log_call_stack_and_traceback(logging.critical)
            self.response.write("Fail")
