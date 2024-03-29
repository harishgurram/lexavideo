
# LexaVideo Copyright information - do not remove this copyright notice
# Copyright (C) 2015 - Alexander Marquardt
#
# LexaVideo -  a fully responsive web-app featuring real-time browser-based video conferencing and text chat.
#
# Original author: Alexander Marquardt
#
# A demo version of LexaVideo can be seen at http://www.chatsurfing.com
#
# Please consider contributing your enhancements and modifications to the LexaVideo community.
# Git source code repository: https://github.com/alexander-marquardt/lexavideo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import webapp2

from google.appengine.api import channel
from google.appengine.ext import ndb

from video_src import clients
from video_src import constants
from video_src import http_helpers
from video_src import messaging
from video_src import chat_room_module
from video_src import video_setup

from error_handling import handle_exceptions

from request_handler_custom.base_handler import  BaseHandlerClientVerified, BaseHandlerUserVerified



class AddClientToRoom(BaseHandlerClientVerified):
    """Handles when a user explicitly enters into a room by going to a URL for a given room."""
    
    @staticmethod
    def add_client_to_room(chat_room_obj, client_id):

        logging.debug('add_client_to_room called for client_id %s and room %s' % (client_id, chat_room_obj))
        client_obj = clients.ClientModel.get_by_id(client_id)


        if chat_room_obj.key in client_obj.list_of_open_chat_rooms_keys:
            client_was_previously_in_this_room = True
        else:
            client_was_previously_in_this_room = False

        (new_client_has_been_added, chat_room_obj) = chat_room_obj.txn_add_client_to_room(client_id)

        client_obj.txn_add_room_key_to_client_status_tracker(chat_room_obj.key)


        if new_client_has_been_added:
            # Send a notification to all room members that a new client has joined the room
            messaging.send_room_occupancy_to_clients(chat_room_obj,
                                                          chat_room_obj.room_members_client_ids,
                                                          recompute_members_from_scratch=True)

            if client_was_previously_in_this_room:
                AddClientToRoom.tell_client_they_were_re_added_to_room_after_they_have_been_absent(client_id, chat_room_obj)


    @staticmethod
    def tell_client_they_were_re_added_to_room_after_they_have_been_absent(client_id, chat_room_obj):
        """
        Used for notifying the client that they have be re-added to
        a room that they had previously been in. This will allow us to show them a message
        indicting that they may have missed some messages while they were absent.
        """

        message_obj = {
            'fromClientId': client_id,
            'chatRoomId': chat_room_obj.key.id(),
            'messageType': 'clientReAddedToRoomAfterAbsence',
            'messagePayload': {},
            }
        logging.debug('Telling client that they were added to room after absence. message_obj: %s' % message_obj)
        channel.send_message(client_id, json.dumps(message_obj))



    @staticmethod
    def add_client_to_all_previously_open_rooms(client_obj):
        """
        Useful for cases where the channel has died, and we wish to ensure that the new client_id
        associated with a user is placed in all of the rooms that the user has open once the client re-joins the room.
        """

        client_id = client_obj.key.id()
        logging.debug('add_client_to_all_users_rooms called for client_id %s' % client_id)

        list_of_open_chat_rooms_keys = client_obj.list_of_open_chat_rooms_keys

        # Loop over all rooms that the user currently has open.
        for room_key in list_of_open_chat_rooms_keys:
            room_id = room_key.id()
            chat_room_obj = chat_room_module.ChatRoomModel.get_room_by_id(room_id)
            room_members_client_ids = chat_room_obj.room_members_client_ids

            # Only add the client to the room if the client is not already in the room (Note: this
            # is also verified inside the transaction, but we don't want to tie-up the transaction
            # with un-necessary calls)
            if client_id not in room_members_client_ids:
                AddClientToRoom.add_client_to_room(chat_room_obj, client_id)




    @handle_exceptions
    def post(self):
        data_object = json.loads(self.request.body)
        client_id = data_object['clientId']
        assert self.session.user_id == int(client_id.split('|')[0])
        room_id = data_object['chatRoomId']

        chat_room_obj = chat_room_module.ChatRoomModel.get_by_id(room_id)
        self.add_client_to_room(chat_room_obj, client_id)

        http_helpers.set_http_ok_json_response(self.response, {})



class RemoveClientFromRoom(BaseHandlerUserVerified):
    # Note: we inherit from BaseHandlerUserVerified as opposed to BaseHandlerClientVerified because
    # we are not totally sure that the client being removed is actually logged in.
    @handle_exceptions
    def post(self):

        post_body_json = json.loads(self.request.body)
        client_id = post_body_json['clientId']
        room_id = post_body_json['chatRoomId']

        chat_room_obj = chat_room_module.ChatRoomModel.get_by_id(room_id)
        chat_room_obj = chat_room_obj.txn_remove_client_from_room(client_id)

        client_obj = clients.ClientModel.get_by_id(client_id)
        if client_obj:
            client_obj.txn_remove_room_from_client_status_tracker(chat_room_obj.key)

        messaging.send_room_occupancy_to_clients(chat_room_obj, chat_room_obj.room_members_client_ids,
                                                 recompute_members_from_scratch=True)

        http_helpers.set_http_ok_json_response(self.response, {})


class SynClientHeartbeat(BaseHandlerClientVerified):
    """Receives a "synchronization heartbeat" from the client, which we respond to on the channel."""

    @handle_exceptions
    def post(self):
        client_id = self.session.client_obj.key.id()

        # Just send a short simple response so that the client can verify if the channel is up.
        response_message_obj = {
            'fromClientId': client_id, # channel-services expects fromClientId to be specified.
            'messageType': 'synAckHeartBeat' # use handshaking terminology for naming
        }

        logging.debug('Heartbeat synchronization received from client_id %s. '
                     'Synchronization acknowledgement returned to same client on channel api' % (client_id))

        channel.send_message(client_id, json.dumps(response_message_obj))

        http_helpers.set_http_ok_json_response(self.response, {})

class UpdateClientStatusAndRequestUpdatedRoomInfo(BaseHandlerClientVerified):
    """
    Called by the client in the following cases:
    1) Acknowledgement to the 'synAckHeartBeat' response that we sent to the client over the channel. In this
       case, we expect the posted 'messageType' to be 'ackHeartbeat'. In this case, presence state will be updated.
    2) Message from the client when the client has changed rooms.

    After this object is posted to, the client will be sent a message on the channel that will contain
    an updated list of all of the clients that are in the room that the client is currently viewing.
    """

    @handle_exceptions
    def post(self):
        message_obj = self.session.post_body_json
        message_type = message_obj['messageType']
        presence_state_name = message_obj['messagePayload']['presenceStateName']
        currently_open_chat_room_id = message_obj['messagePayload']['currentlyOpenChatRoomId']

        client_obj = self.session.client_obj
        client_id = client_obj.key.id()

        # We only update the user presence in the case that this is posted to as an acknowledgement
        # of a heartbeat. If we were to update presence state in other cases, then the memcache and other timeouts
        # that are synchronized to the heartbeat timing would be incorrect (eg. This function is also called when
        # the user changes rooms so that they receive an updated list of room members, but that doesn't mean
        # that their channel is currently up an running -- the channel is only proven to be up if we have received
        # an ackHeartBeat message from the client, as the client sends ackHeartBeat as a response to a
        # synAckHeartBeat message that is sent on the channel)
        if message_type == 'ackHeartbeat':

            # Get the previous presence state, so that we can detect if a user was offline, which would mean
            # that they need to be added back to all of the rooms that they previously had open.
            previous_presence_state = client_obj.get_current_presence_state()

            # Important to update the presence state before adding the client to the rooms, so that they will not
            # be immediately removed from the rooms in the event that we generate a new room members list (which
            # would remove offline clients) at the same time that we are attempting to add the client back to all of the
            # rooms that he previously had open.
            client_obj.store_current_presence_state(presence_state_name)

            if previous_presence_state == 'PRESENCE_OFFLINE':
                # Since the client was offline, they (should) have already been removed from all rooms that they
                # previously had open. Add them back to all rooms since we now know that they are alive.
                logging.info('Client %s had state %s, and is now getting added back to all previously '
                             'open rooms. New client state is %s' %
                             (client_id, previous_presence_state, presence_state_name))
                AddClientToRoom.add_client_to_all_previously_open_rooms(client_obj)

        # Chat room that the client is currently looking at needs an up-to-date view of
        # clients and their activity. Other rooms do not need to be updated as often since the client is not looking
        # at these other rooms right now. Send the client an updated list of the currently viewed room members.
        if currently_open_chat_room_id is not None:
            chat_room_obj = chat_room_module.ChatRoomModel.get_by_id(currently_open_chat_room_id)

            if message_type == 'ackHeartbeat' and client_id not in chat_room_obj.room_members_client_ids:
                # This should not happen, as the above code should have added the client back to any rooms
                # that they opened as soon as he sent a message during a time when his state was
                # considered PRESENCE_OFFLINE.
                logging.error("client_id %s not in chat room %s even though he is requesting an update for that "
                              "room." % (client_id, currently_open_chat_room_id))


            messaging.send_room_occupancy_to_clients(chat_room_obj, [client_id,], recompute_members_from_scratch=False)

        http_helpers.set_http_ok_json_response(self.response, {})


class CreateClientOnServer(BaseHandlerUserVerified):

    @handle_exceptions
    def post(self):
        data_object = json.loads(self.request.body)
        client_id = data_object['clientId']
        assert self.session.user_id == int(client_id.split('|')[0])
        logging.debug('CreateClientOnServer called for client_id: %s' % client_id)

        client_obj = clients.ClientModel.get_by_id(client_id)
        if not client_obj:
            clients.ClientModel.txn_create_new_client_object(client_id)

        http_helpers.set_http_ok_json_response(self.response, {})

class ClientChannelOpened(BaseHandlerClientVerified):

    @classmethod
    def make_sure_client_is_logged_in_correctly(cls, client_obj):

        logging.debug('Ensuring that client %s is logged in correctly' % client_obj.key.id())

        # We need to set the presence of the client so that it is not 'OFFLINE', as this would cause the
        # client to be removed from the rooms that we are going to put the client back into. However,
        # as we don't actually know the state of the user, we just set it to 'PRESENCE_AWAY' which
        # will prevent and inadvertent 'OFFLINE' status from causing the user to be immediately
        # cleared out of the rooms that we are trying to add the user back into.
        if client_obj.get_current_presence_state() == 'PRESENCE_OFFLINE':
            client_obj.store_current_presence_state('PRESENCE_AWAY')

        # Make sure that this client is a member of all of the rooms that he previously had open. This should
        # only needed for the case that the channel has died and started again (Channel can die
        # for many reasons, one of them being a browser refresh)
        AddClientToRoom.add_client_to_all_previously_open_rooms(client_obj)


    # This is post called *manually* by the client-side javascript after it confirms that the channel is connected.
    # Note that the functionality here overlaps with the post handler in ChannelConnected.
    # This is redundant and intentional until we understand better if both of these functions are guaranteed
    # to be correctly called every time the channel is opened.
    @handle_exceptions
    def post(self):
        client_obj = self.session.client_obj
        logging.debug('ClientChannelOpened called for client: %s' % client_obj.key.id())
        ClientChannelOpened.make_sure_client_is_logged_in_correctly(client_obj)


class RequestChannelToken(BaseHandlerClientVerified):

    @handle_exceptions
    def post(self):
        duration_minutes = constants.channel_duration_minutes
        client_id = self.session.client_obj.key.id()
        channel_token = channel.create_channel(str(client_id), duration_minutes)

        logging.debug('New channel token created for client_id: %s' % client_id)

        response_dict = {
            'channelToken': channel_token,
        }

        # Finally, send the http response.
        http_helpers.set_http_ok_json_response(self.response, response_dict)


class ChannelConnected(webapp2.RequestHandler):

    # This is post called *automatically* by the AppEngine any time that the channel is connected.
    # Note that the functionality here overlaps with the post handler in ClientChannelOpened.
    # This is redundant and intentional until we understand better if both of these functions are guaranteed
    # to be correctly called every time the channel is opened.
    @handle_exceptions
    def post(self):

        client_id = self.request.get('from')
        logging.info('ChannelConnected called for client_id: %s' % client_id)
        client_obj = ndb.Key('ClientModel', client_id).get()
        ClientChannelOpened.make_sure_client_is_logged_in_correctly(client_obj)


"""
DisconnectClient will be called when the channel dies (for example if the user leaves the page),
and for immediate execution when a user unloads a page in their browser,
we also manually call this disconnect with an onbeforeunload event handler
in the javascript code.
Therefore, it is possible and even likely that this call will be called multiple
times when a user leaves a page - this should therefore idempotent.
"""
class DisconnectClient(webapp2.RequestHandler):

    @handle_exceptions
    def post(self):

        client_id = self.request.get('from')
        client_obj = clients.ClientModel.get_by_id(client_id)

        logging.warning('client_id: %s has been disconnected' % client_id)

        if client_obj:
            video_setup.VideoSetup.remove_video_setup_objects_containing_client_id(client_id)

            for chat_room_obj_key in client_obj.list_of_open_chat_rooms_keys:
                chat_room_obj = chat_room_obj_key.get()

                if chat_room_obj.has_client(client_id):

                    # Remove the client from the room. However, notice that we don't remove the room from the client's
                    # list_of_open_chat_rooms_keys, because if the channel comes back, we want the client to automatically
                    # join the rooms that he previously had open.
                    chat_room_obj = chat_room_obj.txn_remove_client_from_room(client_id)

                    # This client has disconnected from the room, so we want to send an update to the remote
                    # clients informing them of the new room status.
                    messaging.send_room_occupancy_to_clients(chat_room_obj, chat_room_obj.room_members_client_ids,
                                                             recompute_members_from_scratch=True)

                else:
                    logging.info('Room %s (%d) does not have client %s - probably already removed' % (chat_room_obj.chat_room_name_normalized, chat_room_obj.key.id(), client_id))

        http_helpers.set_http_ok_json_response(self.response, {})

class AutoDisconnectClient(DisconnectClient):
    def post(self):
        logging.debug('Executing AutoDisconnectClient')

        # There seem to be problems with the channel API calling disconnect while the channel is
        # still connected. Therefore, don't run this code, and instead let the user timeout from
        # the chat rooms that they are participating in.
        #super(AutoDisconnectClient, self).post()

class ManuallyDisconnectClient(DisconnectClient):
    def post(self):
        logging.debug('Executing ManuallyDisconnectClient')
        super(ManuallyDisconnectClient, self).post()