
import json
import logging
import webapp2

from google.appengine.ext import ndb

from video_src import messaging
from video_src import models

from video_src.error_handling import handle_exceptions


class RoomName(ndb.Model):
    # This is a class that will be keyed by the room name, and that we use for guaranteeing
    # that each room name is unique. Once a room name has been determined to be unique, then
    # we will write the Room object (below)
    creation_date = ndb.DateTimeProperty(auto_now_add=True)
    pass

# RoomInfo will contain data about which users are currently communicating with each other.
class RoomInfo(ndb.Model):
    """All the data necessary for keeping track of room names and occupancy etc. """

    # This is the lower case room name - ie. user wrote 'Alex', but it will be stored as 'alex'
    room_name = ndb.StringProperty(default = None)

    # The following is used for showing/remembering the room nam as it was written i.e.
    # if the user wrote 'aLeX', it will be stored here as 'aLeX'
    room_name_as_written = ndb.StringProperty(default = None)
    
    # track the users that have joined into a room (ie. opened the URL to join a room)
    room_creator_key = ndb.KeyProperty(kind = models.UserModel)
    room_joiner_key = ndb.KeyProperty(kind = models.UserModel)
    
    # track if the users in the room have a channel open (channel api)
    room_creator_channel_open = ndb.BooleanProperty(default=False)
    room_joiner_channel_open = ndb.BooleanProperty(default=False)
    

    creation_date = ndb.DateTimeProperty(auto_now_add=True)

    def __str__(self):
        result = '['
        if self.room_creator_key:
            result += "%s-%r" % (self.room_creator_key, self.room_creator_channel_open)
        if self.room_joiner_key:
            result += ", %s-%r" % (self.room_joiner_key, self.room_joiner_channel_open)
        result += ']'
        return result


    def make_client_id(self, user_key_id):
        return str(self.key.id()) + '/' + str(user_key_id)


    def remove_user(self, user_id):
        messaging.delete_saved_messages(self.make_client_id(user_id))
        if self.room_joiner_key and user_id == self.room_joiner_key.id():
            self.room_joiner_key = None
            self.room_joiner_channel_open = False
        if self.room_creator_key and user_id == self.room_creator_key.id():
            if self.room_joiner_key:
                self.room_creator_key = self.room_joiner_key
                self.room_creator_channel_open = self.room_joiner_channel_open
                self.room_joiner_key = None
                self.room_joiner_channel_open = False
            else:
                self.room_creator_key = None
                self.room_creator_channel_open = False
        if self.get_occupancy() > 0:
            self.put()
        else:
            self.key.delete()
        

    def get_occupancy(self):
        occupancy = 0
        if self.room_creator_key:
            occupancy += 1
        if self.room_joiner_key:
            occupancy += 1
        return occupancy


    def get_other_user(self, user_id):
        if self.room_creator_key and user_id == self.room_creator_key.id():
            return self.room_joiner_key.id() if self.room_joiner_key else None
        elif self.room_joiner_key and user_id == self.room_joiner_key.id():
            return self.room_creator_key.id() if self.room_creator_key else None
        else:
            return None


    def has_user(self, user_key_id):
        return (user_key_id and (user_key_id == self.room_creator_key.id() or user_key_id == self.room_joiner_key.id()))


    def add_user(self, user_key):
        if not self.room_creator_key:
            self.room_creator_key = user_key
        elif not self.room_joiner_key:
            self.room_joiner_key = user_key
        else:
            raise RuntimeError('room is full')
        
        self.put()


    def set_connected(self, user_key_id):
        if user_key_id == self.room_creator_key.id():
            self.room_creator_channel_open = True
        if user_key_id == self.room_joiner_key.id():
            self.room_joiner_channel_open = True

        self.put()


    def is_connected(self, user_key_id):
        if user_key_id == self.room_creator_key.id():
            return self.room_creator_channel_open
        if user_key_id == self.room_joiner_key.id():
            return self.room_joiner_channel_open
        
    def user_is_room_creator(self, user_key_id):
        return True if user_key_id == self.room_creator_key.id() else False

    def user_is_room_joiner(self, user_key_id):
        return True if user_key_id == self.room_joiner_key.id() else False


def connect_user_to_room(room_key_id, active_user_key_id):

    room_obj = RoomInfo.get_by_id(room_key_id)

    # Check if room has active_user in case that disconnect message comes before
    # connect message with unknown reason, observed with local AppEngine SDK.
    if room_obj and room_obj.has_user(active_user_key_id):
        room_obj.set_connected(active_user_key_id)
        logging.info('User ' + active_user_key_id + ' connected to room ' + room_obj.room_name)
        logging.info('RoomInfo ' + room_obj.room_name + ' has state ' + str(room_obj))
        
        other_user = room_obj.get_other_user(active_user_key_id)
        
        message_obj = {'messageType' : 'roomStatus', 
                       'messagePayload': {
                           'roomName' : room_obj.room_name,
                           'room_creator_key' : room_obj.room_creator_key,
                           'room_joiner_key'  : room_obj.room_joiner_key,
                       }    
                       }
    
        if (other_user):
            # If there is another user already in the room, then the other user should be the creator of the room. 
            # By design, if the creator of a room leaves the room, it should be vacated.
            assert(room_obj.user_is_room_creator(other_user))
            # send a message to the other user (the room creator) that someone has just joined the room
            logging.debug('Sending message to other_user: %s' % repr(message_obj))
            messaging.on_message(room_obj, other_user, json.dumps(message_obj))
            
        # Send a message to the active_user, indicating the "roomStatus"
        logging.debug('Sending message to active_user: %s' % repr(message_obj))
        messaging.on_message(room_obj, active_user_key_id, json.dumps(message_obj))
        
    else:
        logging.warning('Unexpected Connect Message to room ' + room_key_id + 'by user ' + active_user_key_id)
        
    return room_obj


class ConnectPage(webapp2.RequestHandler):
    
    @handle_exceptions
    def post(self):
        key = self.request.get('from')
        room_key_id, user_key_id = key.split('/')

        room = connect_user_to_room(room_key_id, user_key_id)
        if room and room.has_user(user_key_id):
            messaging.send_saved_messages(room.make_client_id(user_key_id))


class DisconnectPage(webapp2.RequestHandler):
    
    @handle_exceptions
    def post(self):
        # temporarily disable disconnect -- this will be replaced with a custom disconnect call from the javascript as opposed to monitoring 
        # the channel stauts.
        pass    

        #key = self.request.get('from')
        #roomName, user = key.split('/')
        #with LOCK:
            #room = RoomInfo.get_by_id(roomName)
            #if room and room.has_user(user):
                #other_user = room.get_other_user(user)
                #room.remove_user(user)
                #logging.info('User ' + user + ' removed from room ' + roomName)
                #logging.info('Room ' + roomName + ' has state ' + str(room))
                #if other_user and other_user != user:

                    #message_object = {"messageType": "sdp",
                                                        #"messagePayload" : {
                                                            #"type" : "bye"
                                                        #}}
                    #channel.send_message(make_client_id(room, other_user),
                                                                #json.dumps(message_object))
                    #logging.info('Sent BYE to ' + other_user)
        #logging.warning('User ' + user + ' disconnected from room ' + roomName)
        

class MessagePage(webapp2.RequestHandler):
    
    @handle_exceptions
    def post(self):
        message = self.request.body
        room_id = int(self.request.get('r'))
        user_id = int(self.request.get('u'))
        room_obj = RoomInfo.get_by_id(room_id)
        if room_obj:
                messaging.handle_message(room_obj, user_id, message)
        else:
            logging.error('Unknown room_id %d' % room_id)