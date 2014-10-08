/**
 * Created by alexandermarquardt on 2014-09-04.
 */



'use strict';

var lxSelectVideoTypePreferenceServices = angular.module('lxVideoNegotiation.services', []);


lxSelectVideoTypePreferenceServices.factory('lxVideoSettingsNegotiationService',
    function(
        $animate,
        $log,
        lxCallService,
        lxMessageService,
        lxWebRtcSessionService)
    {


    var watchRemoteVideoSignalingStatus = function(scope) {
        return function() {
            var returnVal = scope.videoSignalingObject.remoteVideoSignalingStatus.settingsType + ' ' +
                scope.videoSignalingObject.remoteVideoSignalingStatus.videoType;
            //$log.debug('returnVal is "' + returnVal +'"');
            return returnVal;
        };
    };

    var self =  {

        negotiateVideoType :  {
            /* Requests and sets up the type of video that will be transmitted between the two users */

            sendRequestForVideoType : function (videoType) {
                lxMessageService.sendMessage('videoSettings', {settingsType: 'requestVideoType', videoType: videoType});
            },

            sendAcceptanceOfVideoType : function(videoType) {
                // send a message to the remote user to indicate that the local user has accepted their offer to
                // change the current video settings (ie. from asciiVideo to hdVideo).
                lxMessageService.sendMessage('videoSettings', {settingsType: 'acceptVideoType', videoType: videoType});
            },

            sendDenyOfVideoType : function(videoType) {
                // send a message to the remote user to indicate that local user has denied their offer to change the
                // current video settings.
                lxMessageService.sendMessage('videoSettings', {settingsType: 'denyVideoType', videoType: videoType});
            }
        },

        startVideoType: function(scope, videoType) {

            if (videoType === 'HD Video') {
                // once lxCallService has made a successful connection (onRemoteStreamAdded callback is executed),
                // then localIsSendingVideoType will be updated
                lxCallService.maybeStart(scope.localVideoObject, scope.remoteVideoObject, scope.videoSignalingObject);


                // Un-mute the audio in case that the user has just switched from ascii video back to HD video.
                lxCallService.setAudioMute(scope.localVideoObject, false);


                // Note: scope.videoSignalingObject.localIsSendingVideoType will be set to 'HD Video' once the
                // stream is being sent - this happens in the onRemoteStreamAdded callback.

                // Note: HD Video videoSignalingStatusForUserFeedback messages are cleared inside the onRemoteStreamAdded callback
            }
            else if (videoType === 'ASCII Video') {
                // Switch to ASCII video type, and stop  the HD video stream.
                scope.videoSignalingObject.localIsSendingVideoType = videoType;
                scope.videoSignalingObject.remoteIsSendingVideoType = videoType;

                // clear feedback messages - ASCII video transmission will start immediately and therefore
                // user will not see any feedback regarding the transition to ASCII video.
                scope.videoSignalingObject.videoSignalingStatusForUserFeedback = null;

                // kill the webRtc session. Ascii video should start to be transmitted in both directions.
                lxWebRtcSessionService.stop();

                // mute the audio - this should technically not be necessary, but for some reason during a firefox to chrome session
                // the audio continues to transmit even though the rtcSession was stopped.
                lxCallService.setAudioMute(scope.localVideoObject, true);
            }
            else {
                $log.error('Unknown video type received: ' + videoType);
            }
        },

        /*
         This function will monitor the type of video that the local user and that the remote user have
         selected for sending between them. This requires some message exchanges before the video type will
         be finalized.
         We are more strict about sending hd video than ascii video. If ascii video is selected by one of the
         parties in a video call, then both sides will automatically switch over to ascii video. If they wish
         to switch to HD video, then a request will be sent from one user to the other, and the other user
         will have to agree to send HD video before transmission will begin.
         The messages that will be shown to the users can be seen in lx-video-negotiation-directives.
         */
        watchForVideoSettingsChanges : function(scope) {


            // Monitor localIsNegotiatingForVideoType for changes, and if it changes then initiate an exchange with the remote
            // peer to star to exchange the newly selected video type.
            // Note: since we may set the localIsNegotiatingForVideoType value upon accepting a remote request to change the
            // video type, this watch may also be executed for clients that did not explicitly press the button to change
            // the current video type. This may require some attention in the case that a client that has received a request
            // and sent an acceptance of a particular video type, may also then send a duplicate request for that same
            // video type. This duplicate request is harmless and should be ignored by the recipient.
            scope.$watch('videoSignalingObject.localIsNegotiatingForVideoType', function(localIsNegotiatingForVideoType) {

                // if the user has not explicitly requested a modification to the video type by pressing on one of the
                // buttons, then localIsNegotiatingForVideoType should be null and this code should not be executed.
                if (localIsNegotiatingForVideoType !== null) {

                    // Check if there is a remote user in the room
                    if (scope.videoSignalingObject.remoteUserId) {

                        if (localIsNegotiatingForVideoType === 'HD Video' || localIsNegotiatingForVideoType === 'ASCII Video') {

                            // remove the user feedback indicating that we are waiting for the remote user
                            // to accept HD video
                            scope.videoSignalingObject.videoSignalingStatusForUserFeedback = 'waitingForRemoteToAcceptVideoType: ' + localIsNegotiatingForVideoType;

                            // No need to re-negotiate the videoType, since we have just set it back to a previous value due to
                            // a remote denial for a proposed new videoType.
                            self.negotiateVideoType.sendRequestForVideoType(scope.videoSignalingObject.localIsNegotiatingForVideoType);

                        }
                        else {
                            $log.error('Unknown videoType: ' + localIsNegotiatingForVideoType);
                        }
                    }

                    // The current user is alone in the room
                    else {
                        scope.videoSignalingObject.videoSignalingStatusForUserFeedback = 'waitingForRemoteUserToJoin';

                        // Send an 'accept' of the selected videoType to the server -- this will cause the room
                        // to update it's value stored for 'currently_selected_video_type'. Future joiners to
                        // the room will have their videoType initialized to this value.
                        self.negotiateVideoType.sendAcceptanceOfVideoType(localIsNegotiatingForVideoType);


                        // set localIsSendingVideoType to localIsNegotiatingForVideoType so that they will be shown the
                        // correct video windows.
                        scope.videoSignalingObject.localIsSendingVideoType = localIsNegotiatingForVideoType;
                    }
                }
            });


            // Monitor remoteUserId to track if the remote user is currently in the room, or out of it
            scope.$watch('videoSignalingObject.remoteUserId', function(newRemoteUserId, oldRemoteUserId) {
                if (newRemoteUserId === null && oldRemoteUserId) {
                    scope.videoSignalingObject.videoSignalingStatusForUserFeedback = 'remoteUserHasLeftRoom';
                }

                if (newRemoteUserId === null) {
                    // remote user is not connected, so set the signaling status to null
                    scope.videoSignalingObject.remoteVideoSignalingStatus.settingsType = null;
                    scope.videoSignalingObject.remoteVideoSignalingStatus.videoType = null;

                    // remote user is not connected, so set the sending videoType to null
                    scope.videoSignalingObject.remoteIsSendingVideoType = null;
                }
            });

//            Object.observe(scope.videoSignalingObject.remoteVideoSignalingStatus, function(changes) {
//                $log.debug('Changes: ' + angular.toJson(changes));
//            });

            // This watcher will monitor for remote requests to change the current video format, and will either
            // respond directly, or modify a variable that will trigger another watcher that will request user
            // feedback on how to respond. More details in the comments below.
            scope.$watch(watchRemoteVideoSignalingStatus(scope), function() {

                var remoteSignalingStatus = scope.videoSignalingObject.remoteVideoSignalingStatus;
                var localHasSelectedVideoType = scope.videoSignalingObject.localHasSelectedVideoType;

                if (remoteSignalingStatus.settingsType === 'requestVideoType') {
                    // the remote user has requested a new videoType.

                    if (remoteSignalingStatus.videoType === localHasSelectedVideoType) {
                        // the remote user has requested the videoType that the local user has already selected.

                        self.negotiateVideoType.sendAcceptanceOfVideoType(remoteSignalingStatus.videoType);
                        $log.debug('Automatically accepting video type ' + remoteSignalingStatus.videoType + ' since it was already selected locally. ');

                        self.startVideoType(scope, localHasSelectedVideoType);

                    }
                    else {

                        // remote user has requested that the local user send a video type that is different from
                        // what the local user is currently sending.
                        $log.debug('Remote user has requested ' + remoteSignalingStatus.videoType);


                        // We prompt the local user to see if they agree to transmit the new videoType.
                        // This prompting is triggered by the change in
                        // videoSignalingStatusForUserFeedback and is handled in the directive code.
                        if (remoteSignalingStatus.videoType === 'HD Video' || remoteSignalingStatus.videoType === 'ASCII Video') {
                            scope.videoSignalingObject.videoSignalingStatusForUserFeedback = 'remoteHasRequestedVideoType: ' + remoteSignalingStatus.videoType;
                        }

                        else {
                            $log.log('Error: unknown remoteSignalingStatus.videoType: ' + remoteSignalingStatus.videoType);
                        }
                    }

                }

                else if (remoteSignalingStatus.settingsType === 'denyVideoType') {

                    $log.debug('Remote user has denied ' + remoteSignalingStatus.videoType);
                    scope.videoSignalingObject.videoSignalingStatusForUserFeedback = 'remoteHasDeniedRequestToExchangeFormat: ' + remoteSignalingStatus.videoType;

                    // since the request to transmit a new format was denied, change the localHasSelectedVideoType back
                    // to the type that is currently/previously being sent - this will change the button that the user
                    // has clicked on back to it's previous state.
                    scope.videoSignalingObject.localHasSelectedVideoType = scope.videoSignalingObject.localIsSendingVideoType;

                    // we have finished with the current request, and are no longer requesting a new videoType.
                    scope.videoSignalingObject.localIsNegotiatingForVideoType = null;
                }

                else if (remoteSignalingStatus.settingsType === 'acceptVideoType') {
                    // remote user has sent an acceptance of the requested videoType

                    // ensure that the videoType that the remote user has accepted matches the value that has been
                    // selected by the local user.
                    $log.debug('Remote user has accepted ' + remoteSignalingStatus.videoType);
                    if (remoteSignalingStatus.videoType === localHasSelectedVideoType) {

                        self.startVideoType(scope, localHasSelectedVideoType);

                        // we have finished with the current request, and are no longer requesting a new videoType.
                        scope.videoSignalingObject.localIsNegotiatingForVideoType = null;

                    } else {
                        scope.videoSignalingObject.videoSignalingStatusForUserFeedback = 'conflictingVideoTypes';
                        $log.warn('videoType mismatch.');
                    }
                }

                // Set the remoteSignalingStatus properties to null, so that this watch will be triggered
                // when the remote user sends us a new request, even if this is the same request that they previously
                // sent to us.
                // Note: if we do not reset these values , then future requests that are the same as the most recent request
                // will not trigger execution of this watch function, which means that the local user would not see any new
                // requests that are the same as a previous request that they have already responded to.
                scope.videoSignalingObject.remoteVideoSignalingStatus.settingsType = null;

            });
        }
    };
    return self;
});