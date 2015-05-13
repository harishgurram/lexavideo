# Much of this code is originally from:
# http://blog.abahgat.com/2013/01/07/user-authentication-with-webapp2-on-google-app-engine/

import datetime

import webapp2
from webapp2_extras import auth

import gaesessions
from video_src import constants

def user_required(handler):
    """
      Decorator that checks if there's a user associated with the current session.
      Will also fail if there's no session present.
    """
    def check_login(self, *args, **kwargs):
        auth = self.auth
        if not auth.get_user_by_session():
            self.redirect(self.uri_for('login'), abort=True)
        else:
            return handler(self, *args, **kwargs)

    return check_login

class BaseHandler(webapp2.RequestHandler):
    @webapp2.cached_property
    def auth(self):
        """Shortcut to access the auth instance as a property."""
        return auth.get_auth()


    @webapp2.cached_property
    def user_obj(self):
        """Shortcut to access the current logged in user.

        Fetches information from the persistence layer and
        returns an instance of the underlying model.

        :returns
          The instance of the user model associated to the logged in user.
        """
        user_id = self.session['user_id']
        user_obj = self.user_model.get_by_id(user_id)
        return user_obj

    @webapp2.cached_property
    def user_model(self):
        """Returns the implementation of the user model.

        It is consistent with config['webapp2_extras.auth']['user_model'], if set.
        """
        return self.auth.store.user_model


    # this is needed for webapp2 sessions to work. Note, we use gaesessions instead of webapp2 sessions
    # to track our user sessions.
    def dispatch(self):
        lifetime = datetime.timedelta(minutes=60)

        # Get a session for this request
        # Since we are not passing an "sid" to Session, the session will be read from a cookie.
        # If there is no session associated with the cookie, then the session will remain unset until
        # it is written (eg. by executing "self.session['user_id'] = user_id"), at which point
        # a new session id will be assigned and the session is created.
        self.session = gaesessions.Session(lifetime=lifetime, cookie_key=constants.secret_key)

        try:
            # Dispatch the request.
            webapp2.RequestHandler.dispatch(self)
        finally:
            # Save the session
            self.session.save()

            # update the response to contain the cookie
            for ch in self.session.make_cookie_headers():
                self.response.headers.add('Set-Cookie', ch)

