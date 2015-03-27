'use strict';

/* global goog */

angular.module('lxChannel.services', [])


    .service('lxChannelMessageService', function() {
        var msgQueue = {};

        function makeSureQueueExists(remoteClientId) {
            if (!(remoteClientId in msgQueue)) {
                    msgQueue[remoteClientId] = [];
            }
        }

        return {
            clearQueue : function(remoteClientId) {
                makeSureQueueExists(remoteClientId);
                msgQueue[remoteClientId].length = 0;
            },
            unshift : function(remoteClientId, msg) {
                // adds the msg to the beginning of the array.
                makeSureQueueExists(remoteClientId);
                return msgQueue[remoteClientId].unshift(msg);
            },
            push: function(remoteClientId, msg) {
                makeSureQueueExists(remoteClientId);
                // adds the msg to the end of the array.
                return msgQueue[remoteClientId].push(msg);
            },
            shift : function(remoteClientId) {
                makeSureQueueExists(remoteClientId);
                // pull the first element out of the array and return it.
                return msgQueue[remoteClientId].shift();
            },
            getQueueLength : function(remoteClientId) {
                makeSureQueueExists(remoteClientId);
                return msgQueue[remoteClientId].length;
            }
        };
    })

    .service('lxChannelSupportService', function() {
        this.channelReady = false;
        this.socket = null;
    })

    .factory('lxChannelService',
    function($log,
             $timeout,
             $rootScope,
             lxAccessVideoElementsAndAccessCameraService,
             lxAppWideConstantsService,
             lxCallService,
             lxChannelMessageService,
             lxChannelSupportService,
             lxCreateChatRoomObjectsService,
             lxHttpChannelService,
             lxJs,
             lxMessageService,
             lxWebRtcSessionService

             ) {

        /*
         Provides functionality for opening up and handling callbacks from the Google App-engine "Channel API".
         */

        var onChannelOpened = function() {
            return function () {
                $log.log('Channel opened.');
                lxChannelSupportService.channelReady = true;
            };
        };

        var onChannelMessage = function(self, scope) {
            return function(message) {

                var localVideoObject = scope.localVideoObject;

                $rootScope.$apply(function() {
                    var messageObject = JSON.parse(message.data);
                    var remoteClientId = messageObject.fromClientId;
                    var remoteVideoObject = scope.remoteVideoObjectsDict[remoteClientId];
                    var chatRoomId = null;

                    lxJs.assert(remoteClientId, 'remoteClientId is not set');

                    switch (messageObject.messageType) {
                        case 'sdp':
                            //$log.debug('S->C: ' + message.data);

                            var sdpObject = messageObject.messagePayload;


                            if (!scope.videoExchangeObjectsDict[remoteClientId].rtcInitiator && !lxWebRtcSessionService.webRtcSessionStarted[remoteClientId]) {
                                // Callee is the client that is *not* the rtcInitiator (the rtcInitiator calls
                                // the callee). The callee will only start negotiating video connection if they
                                // receive an "offer" from the caller.

                                if (sdpObject.type === 'offer') {
                                    // Add offer to the beginning of msgQueue, since we can't handle
                                    // Early candidates before offer at present.
                                    lxChannelMessageService.unshift(remoteClientId, sdpObject);

                                    lxWebRtcSessionService.signalingReady[remoteClientId] = true;
                                    $log.debug('lxWebRtcSessionService.signalingReady = true');

                                    // We may have been waiting for signalingReady to be true to attempt to start the peer-to-peer video
                                    // call because this user is not the rtcInitiator.
                                    lxCallService.maybeStart(scope, remoteClientId);
                                }

                                // Since the turn response is async and also GAE might disorder the
                                // Message delivery due to possible datastore query at server side,
                                // So callee needs to cache messages before peerConnection is created.
                                else {
                                    lxChannelMessageService.push(remoteClientId, sdpObject);
                                }
                            } else {
                                lxWebRtcSessionService.processSignalingMessage(sdpObject, localVideoObject,
                                    remoteVideoObject, scope.lxMainViewCtrl.clientId, remoteClientId);
                            }
                            break;




                        case 'roomOccupancyMsg':
                            var normalizedChatRoomName = messageObject.messagePayload.normalizedChatRoomName;
                            var chatRoomNameAsWritten = messageObject.messagePayload.chatRoomNameAsWritten;
                            chatRoomId = messageObject.messagePayload.chatRoomId;
                            var roomOccupancyDict = scope.roomOccupancyDict;
                            roomOccupancyDict[normalizedChatRoomName] = {};

                            roomOccupancyDict[normalizedChatRoomName].chatRoomNameAsWritten = chatRoomNameAsWritten;
                            roomOccupancyDict[normalizedChatRoomName].chatRoomId = chatRoomId;

                            // status of who is currently in the room.
                            $log.debug('Room status received: ' + JSON.stringify(messageObject.messagePayload));
                            roomOccupancyDict[normalizedChatRoomName].dictOfClientObjects = messageObject.messagePayload.dictOfClientObjects;

                            // copy the dictOfClientObjects into a listOfClientObjects, which is more convenient
                            // for some functions.
                            roomOccupancyDict[normalizedChatRoomName].listOfClientObjects = [];
                            angular.forEach(roomOccupancyDict[normalizedChatRoomName].dictOfClientObjects, function(clientObject, clientId) {
                                // manually add the clientId into the clientObject
                                clientObject.clientId = clientId;
                                roomOccupancyDict[normalizedChatRoomName].listOfClientObjects.push(clientObject);
                            });

                            break;

                        case 'roomInitialVideoSettingsMsg':

                            // See server-side code for more info on rtcInitiator. Basically, if rtcInitiator is sent to the
                            // client, it means that we should attempt to initiate a new rtc connection from scratch once
                            // all pre-conditions are in place for setting up. We do it like this to effectively
                            // deal with page reloads, or with someone leaving a room and then another person joining
                            // that same room -- rtcInitiator is dynamically set on the server depending on if the
                            // person is joining a room, or if the person is already in a room.
                            if ('rtcInitiator' in messageObject.messagePayload) {

                                // Kill the current webRtc session - this is probably not strictly necessary, and could be removed
                                // if it is found to cause delays and/or any other problems.
                                lxWebRtcSessionService.stop(remoteClientId);

                                // Update the value of rtcInitiator that will be accessed throughout the code.
                                scope.videoExchangeObjectsDict[remoteClientId].rtcInitiator = messageObject.messagePayload.rtcInitiator;

                                // signalingReady will initially be set to be true if this is
                                // the rtcInitiator, or false otherwise. In the case that this value is initially false, it will be set to
                                // true once this client has received an sdp 'offer' from the other client.
                                // Note: rtcInitiator is the 2nd client to start their video
                                lxWebRtcSessionService.signalingReady[remoteClientId] = messageObject.messagePayload.rtcInitiator;

                                // when the server sends an rtcInitiator setting, this means that we are re-starting
                                // the rtc negotiation and peer setup etc. from scratch. Set the following to false
                                // so that the code inside maybeStart will execute all of the initializations that
                                // are required for a new peer session.
                                lxWebRtcSessionService.webRtcSessionStarted[remoteClientId] = false;

                                lxCallService.maybeStart(scope, remoteClientId);

                            }
                            break;

                        case 'chatDataMsg':
                            chatRoomId = messageObject.roomId;
                            var receivedChatMessageObject = scope.receivedChatMessageObject[chatRoomId];

                            receivedChatMessageObject.messageString = messageObject.messagePayload.messageString;
                            // receivedMessageTime is used for triggering the watcher
                            receivedChatMessageObject.receivedMessageTime = new Date().getTime();
                            break;

                        case 'videoExchangeStatusMsg':

                            var isANewRequest = false;
                            if (!(remoteClientId in scope.videoExchangeObjectsDict)) {
                                $log.info('videoExchangeStatusMsg causing creation of new videoExchangeObjectsDict entry for client ' + remoteClientId);
                                scope.videoExchangeObjectsDict[remoteClientId] = lxCreateChatRoomObjectsService.createVideoExchangeSettingsObject();
                                isANewRequest = true;
                            }
                            var localVideoEnabledSetting = scope.videoExchangeObjectsDict[remoteClientId].localVideoEnabledSetting;
                            var newRemoteVideoEnabledSetting = messageObject.messagePayload.videoElementsEnabledAndCameraAccessRequested;
                            scope.videoExchangeObjectsDict[remoteClientId].remoteVideoEnabledSetting = newRemoteVideoEnabledSetting;


                            // If the remote user has requested to start video, and the local user has not responded
                            // then we need to increment the counter that track the number of video sessions not
                            // yet responded to.
                            if (isANewRequest && newRemoteVideoEnabledSetting === 'enableVideoExchange') {
                                 scope.videoStateInfoObject.numVideoRequestsPendingFromRemoteUsers ++;
                                 scope.notificationMenuObject.drawAttentionToNotificationMenuButton = true;
                            }

                            // if remote user requested to exchange video, and then changed their mind, then
                            // we need to remove the previous request from the counter.
                            if (localVideoEnabledSetting === 'waitingForEnableVideoExchangePermission' &&
                                newRemoteVideoEnabledSetting !== 'enableVideoExchange') {
                                 scope.videoStateInfoObject.numVideoRequestsPendingFromRemoteUsers --;
                            }

                            // If the local user has denied video activation (as indicated by localVideoEnabledSetting
                            // of 'doNotEnableVideoExchange'),
                            // then by construction this was triggered by a remoteVideoEnabledSetting of 'enableVideoExchange' .
                            // If the  remote user now has a status other than 'enableVideoExchange' then they are not currently
                            // attempting to exchange video, and the doNotEnableVideoExchange that we previously selected
                            // is no longer applicable (since the remote request is no longer pending)
                            // Reset localVideoEnabledSetting to 'waitingForEnableVideoExchangePermission' so that the remote user will
                            // be able to send a future request to the local user to enable (or deny) access to their video
                            // elements.
                            if (scope.videoExchangeObjectsDict[remoteClientId].remoteVideoEnabledSetting !== 'enableVideoExchange' &&
                                scope.videoExchangeObjectsDict[remoteClientId].localVideoEnabledSetting === 'doNotEnableVideoExchange') {

                                scope.videoExchangeObjectsDict[remoteClientId].localVideoEnabledSetting = 'waitingForEnableVideoExchangePermission';
                            }

                            break;

                        default:
                            $log.error('Error: Unkonwn messageType received on Channel: ' + JSON.stringify(messageObject));
                    }
                });

            };
        };

        var onChannelError = function() {
            $log.error('*** Channel error. ***');
            // lxChannelSupportService.channelReady = false;
        };

        var onChannelClosed = function() {
            $log.warn('*** Channel closed. ***');
            lxChannelSupportService.channelReady = false;
        };

        var handler = function(self, scope) {
            return {
                'onopen': onChannelOpened(),
                'onmessage': onChannelMessage(self, scope),
                'onerror': onChannelError,
                'onclose': onChannelClosed
            };
        };

        return {
            openChannel: function(scope) {

                $log.info('*** Opening channel. ***');
                try {
                    var channel = new goog.appengine.Channel(scope.lxMainViewCtrl.channelToken);
                    lxChannelSupportService.socket = channel.open(handler(this, scope));

                } catch(e) {
                    e.message = '\n\tError in openChannel\n\t' + e.message;
                    $log.error(e);
                }
            }

//            startClientHeartbeat: function(clientId) {
//                lxHttpChannelService.sendClientHeartbeat(clientId);
//                var timeoutFn = function() {
//                    $timeout(function() {
//                        lxHttpChannelService.sendClientHeartbeat(clientId);
//                        timeoutFn();
//                    }, lxAppWideConstantsService.heartbeatIntervalMilliseconds);
//                };
//                timeoutFn();
//            }
        };
    });

