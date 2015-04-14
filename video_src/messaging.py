
import json
import logging
import webapp2

from google.appengine.api import channel

from video_src import chat_room_module
from video_src import http_helpers
from video_src import video_setup


from error_handling import handle_exceptions



# def delete_saved_messages(client_id):
#     messages =models.Message.get_saved_messages(client_id)
#     for message in messages:
#         message.key.delete()
#         logging.info('Deleted the saved message for ' + client_id)


# def send_saved_messages(client_id):
#     messages = models.Message.get_saved_messages(client_id)
#     for message in messages:
#         channel.send_message(client_id, message.msg)
#         logging.info('Delivered saved message to ' + client_id)
#         message.key.delete()


# Sends information about who is in the room
@handle_exceptions
def send_room_occupancy_to_room_clients(chat_room_obj):
    # This is called when a user either connects or disconnects from a room. It sends information
    # to room members indicating the status of who is in the room.

    message_obj = {
        'fromClientId': 'msgSentFromServer',
        'messageType': 'roomOccupancyMsg',
        'messagePayload': {
            'normalizedChatRoomName': chat_room_obj.normalized_chat_room_name,
            'chatRoomNameAsWritten': chat_room_obj.chat_room_name_as_written,
            'chatRoomId': chat_room_obj.key.id(),
            },
        }

    # Javascript needs to know which users are in this room.
    # first we must create a list that contains information of all users that are in the current room.
    dict_of_js_client_objects = {}
    for client_id in chat_room_obj.room_members_client_ids:

    # We only send relevant data to the client,
    # which includes the client_id and the user_name.
        js_user_obj = {
            'userName': client_id,
        }

        dict_of_js_client_objects[client_id] = js_user_obj

    # send list_of_js_user_objects to every user in the room
    for i in range(len(chat_room_obj.room_members_client_ids)):
        client_id = chat_room_obj.room_members_client_ids[i]
        message_obj['messagePayload']['dictOfClientObjects'] = dict_of_js_client_objects

        logging.info('Sending roomOccupancy to %s: %s' % (client_id, json.dumps(message_obj)))
        channel.send_message(client_id, json.dumps(message_obj))

# Sends information about video settings, and which client should be designated as the 'rtcInitiator'
@handle_exceptions
def send_video_call_settings_to_participants(from_client_id, to_client_id):

    vid_setup_id = video_setup.VideoSetup.get_vid_setup_id_for_client_id_pair(from_client_id, to_client_id)
    vid_setup_obj = video_setup.VideoSetup.get_by_id(vid_setup_id)

    count_of_clients_exchanging_video = len(vid_setup_obj.video_elements_enabled_client_ids)

    # Check if there are two people in the room that have enabled video, and if so send
    # a message to each of them to start the webRtc negotiation.
    assert(count_of_clients_exchanging_video <= 2)

    # Once both clients have agreed to send video to each other, then we send the signaling to them
    # to re-start the video setup.
    if count_of_clients_exchanging_video == 2:

        is_initiator = False

        for client_id in vid_setup_obj.video_elements_enabled_client_ids:

            if client_id != from_client_id:
                remote_client_id = from_client_id
            else:
                remote_client_id = to_client_id

            # The second person to connect will be the 'rtcInitiator'.
            # By sending this 'rtcInitiator' value to the clients, this will re-initiate
            # the code for setting up a peer-to-peer rtc session. Therefore, this should only be sent
            # once per session, unless the users become disconnected and need to re-connect.
            message_obj = {'messageType': 'roomInitialVideoSettingsMsg',
                           'fromClientId': remote_client_id,
                           'messagePayload': {'rtcInitiator': is_initiator},
                           }

            logging.info('Sending client %s room status %s' % (client_id, json.dumps(message_obj)))
            channel.send_message(client_id, json.dumps(message_obj))
            is_initiator = not is_initiator




class MessageRoom(webapp2.RequestHandler):

    # Do not place @handle_exceptions here -- exceptions should be dealt with by the functions that call this function
    def handle_message_room(self, chat_room_obj, from_client_id, message_obj):
        # This function passes a message from one user in a given "room" to the other user in the same room.
        # It is used for exchanging sdp (session description protocol) data for setting up sessions, as well
        # as for passing video and other information from one user to the other.

        # If to_client_id is "sendMsgToEveryoneInTheChatRoom", then the message will be sent to all room members, otherwise it will be sent
        # only to the indicated client.
        to_client_ids_list = chat_room_obj.get_list_of_other_client_ids(from_client_id)

        for to_client_id in to_client_ids_list:
            channel.send_message(to_client_id, json.dumps(message_obj))


    @handle_exceptions
    def post(self):
        message = self.request.body
        message_obj = json.loads(message)

        room_id = message_obj['chatRoomId']
        from_client_id = message_obj['fromClientId']

        try:
            chat_room_obj = chat_room_module.ChatRoomModel.get_by_id(room_id)
            if chat_room_obj:
                self.handle_message_room(chat_room_obj, from_client_id, message_obj)
            else:
                logging.error('Unknown room_id %d' % room_id)
                raise Exception('unknownRoomId')


        except:
            status_string = 'Server error'
            http_status_code = 500
            logging_function = logging.error

            http_helpers.set_error_json_response_and_write_log(self.response, status_string, logging_function,
                                                               http_status_code, self.request)


class MessageClient(webapp2.RequestHandler):



    # Do not place @handle_exceptions here -- exceptions should be dealt with by the functions that call this function
    def handle_message_client(self, from_client_id, message_obj):
        # This function passes a message from one user in a given "room" to the other user in the same room.
        # It is used for exchanging sdp (session description protocol) data for setting up sessions, as well
        # as for passing video and other information from one user to the other.

        to_client_id = message_obj['toClientId']
        message_type = message_obj['messageType']
        message_payload = message_obj['messagePayload']

        if message_type == 'videoExchangeStatusMsg':

            logging.info('user %s videoElementsEnabledAndCameraAccessRequested is: %s ' %
                         (from_client_id, message_payload['videoElementsEnabledAndCameraAccessRequested']))

            if message_payload['videoElementsEnabledAndCameraAccessRequested'] == 'doVideoExchange':

                video_setup.VideoSetup.txn_add_user_id_to_video_elements_enabled_client_ids(from_client_id, to_client_id )
                send_video_call_settings_to_participants(from_client_id, to_client_id)
            else:
                video_setup.VideoSetup.txn_remove_user_id_from_video_elements_enabled_client_ids(from_client_id, to_client_id )

            if message_type == 'sdp' and message_payload['type'] == 'offer':
                # This is just for debugging
                logging.info('sdp offer. Payload: %s' % repr(message_payload))

        logging.info('\n***\nSending message to client %s: %s\n' % (to_client_id,  json.dumps(message_obj)))
        channel.send_message(to_client_id, json.dumps(message_obj))

    @handle_exceptions
    def post(self):
        message = self.request.body
        message_obj = json.loads(message)
        from_client_id = message_obj['fromClientId']

        try:
            self.handle_message_client(from_client_id, message_obj)

        except:
            status_string = 'Unknown server error'
            http_status_code = 500
            logging_function = logging.error

            http_helpers.set_error_json_response_and_write_log(self.response, status_string, logging_function,
                                                               http_status_code, self.request)
