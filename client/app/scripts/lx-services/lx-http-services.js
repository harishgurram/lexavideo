'use strict';

angular.module('lxHttp.services', [])

    .factory('lxHttpHandleRoomService',
    function (
        $log,
        $http
        ) {


        return {
            enterIntoRoom : function(roomObj) {
                // this will either create a room object on the server, or enter into an existing room corresponding
                // to chatRoomName.
                // Note: the returned value is a promise that will be fulfilled once the resource
                // has been created on the server.
                var url = '/_lx/handle_room/';
                var httpPromise = $http.post(url, roomObj);
                return httpPromise;
            },


            checkIfRoomExists : function(chatRoomNameAsWritten) {

                var httpPromise = null;
                if (chatRoomNameAsWritten) {
                    var url = '/_lx/check_if_chat_room_exists/' + chatRoomNameAsWritten;
                    httpPromise = $http.get(url);
                }
                return httpPromise;
            }
        };
    })
    .factory('lxHttpChannelService',
    function (
        $log,
        $http,
        lxChannelSupportService,
        lxJs
        ) {

        return {

            // this function will be periodically called so that that room will be up-to-date with the users
            // that are currently in the room.
            sendClientHeartbeat: function(clientId) {
                var postData = {'clientId': clientId};
                $http.post('/_lx/channel/user_heartbeat/', postData);
            },

            addClientToRoom: function(clientId, userId, roomId) {
                lxJs.assert(clientId, 'clientId not set');
                lxJs.assert(userId, 'userId not set');
                lxJs.assert(roomId, 'roomId not set');

                var postData = {
                    'clientId': clientId,
                    'userId': userId,
                    'roomId': roomId
                };
                $http.post('/_lx/add_client_to_room/', postData);
            },

            // Function that will initialize the channel and get the token from the server
            requestChannelToken: function(clientId, userId) {
                var postData = {
                    'clientId': clientId,
                    'userId': userId
                };
                var httpPromise = $http.post('/_lx/channel/request_channel_token/', postData);
                httpPromise.then(function(response){
                    $log.info('Got channel data: ' + response.data);
                }, function(response){
                    $log.error('Failed to open channel for client id: ' + clientId +'\nStatus: ' + response.statusText +
                    '\ndata: ' + angular.toJson(response.data));
                });

                return httpPromise;
            },

            manuallyDisconnectChannel: function(clientId) {
                // If we know that the user is disconnecting from the page, then we may want to send
                // a message to the server immediately, so that the room will be vacated instantly. This
                // is useful for cases where the user clicks on the reload button so that they are removed
                // from the room before the attempt to reload the page is made.

                $http.post('/_lx/channel/manual_disconnect/', 'from=' + clientId, {
                    // post as form data, not as the default json
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded;'}
                }).success(function(){
                    $log.info('Successfully send manual disconnect to server for clientId: ' + clientId);
                }).error(function(){
                    $log.warn('Failed to send manual disconnect to server for clientId: ' + clientId);
                });

                // close the socket
                lxChannelSupportService.socket.close();
            }
        };
    })

    .factory('lxMessageService',
    function(
        $http,
        $log,
        lxChatRoomVarsService,
        lxJs)
    {

        /*
         Functionality for posting messages to the server.
         */
        return {
            broadcastMessageToRoomFn : function(messageType, messagePayload, fromClientId, roomId) {
                /*
                 messageType: string indicating if this is a Signaling message or some other kind of message
                 that is being sent over the Appengine Channel API.
                 Allowed values:
                 'chat' - chat messages sent through the server
                 messagePayload: an object containing data that will be send from one peer to another through the server.
                 Note: this data will be serialized automatically by AngularJS into a JSON object/string.
                 */

                lxJs.assert(fromClientId, 'fromClientId is not set');
                lxJs.assert(roomId, 'roomId is not set');

                var messageObject = {
                    'roomId': roomId,
                    'fromClientId': fromClientId,
                    'messageType': messageType,
                    'messagePayload': messagePayload
                };

                var path = '/_lx/message_room';
                var httpPromise = $http.post(path, messageObject);
                return httpPromise;
            },

            sendMessageToClientFn : function(messageType, messagePayload, fromClientId, toClientId) {
                /*
                 messageType: string indicating if this is a Signaling message or some other kind of message
                 that is being sent over the Appengine Channel API.
                 Allowed values:
                 'sdp' - setting up peer to peer connection
                 'video' - sending video/images through the server
                 messagePayload: an object containing data that will be send from one peer to another through the server.
                 Note: this data will be serialized automatically by AngularJS into a JSON object/string.
                 */

                lxJs.assert(toClientId, 'toClientId is not set');
                lxJs.assert(fromClientId, 'fromClientId is not set');

                var messageObject = {
                    'fromClientId': fromClientId,
                    'toClientId': toClientId,
                    'messageType': messageType,
                    'messagePayload': messagePayload
                };

                //$log.debug('C->S: ' + angular.toJson(messagePayload));
                // NOTE: AppRTCClient.java searches & parses this line; update there when
                // changing here.
                var path = '/_lx/message_client';

                var httpPromise = $http.post(path, messageObject);
                return httpPromise;
            }
        };
    }
);
