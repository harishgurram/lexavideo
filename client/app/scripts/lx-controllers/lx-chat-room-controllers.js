/**
 * Created by alexandermarquardt on 2014-07-08.
 */
'use strict';

// define externally defined variables so that jshint doesn't give warnings
/* global videoConstantsEmbeddedInHtml */

angular.module('lxUseChatRoom.controllers', [])


    .controller('lxChatRoomOuterCtrl',
    function($scope,
             lxAppWideConstantsService,
             lxUseChatRoomConstantsService,
             lxUseChatRoomVarsService,
             lxInitializeRoomService) {

        // Copy all of the values that were embedded in the html into the lxUseChatRoomConstantsService.
        // Do this before everything else, as many other functions require that this structure be setup!!
        angular.extend(lxUseChatRoomConstantsService, videoConstantsEmbeddedInHtml);
        // update the global vars that depend on lxUseChatRoomConstantsService
        lxUseChatRoomVarsService.doUpdate(lxUseChatRoomConstantsService.pcConfig);

        $scope.debugBuildEnabled = lxAppWideConstantsService.debugBuildEnabled;

        $scope.lxChatRoomOuterCtrl = {};

        lxInitializeRoomService.addUserToRoomAndSetupChannel().then(function(data) {

            $scope.lxChatRoomOuterCtrl.userSuccessfullyEnteredRoom  = true;
            $scope.lxChatRoomOuterCtrl.channelToken = data.channelToken;
            $scope.lxChatRoomOuterCtrl.clientId = data.clientId;

            $scope.roomId = lxUseChatRoomVarsService.roomId = data.roomId;

        }, function(reason) {
            // This message should never be seen by the user since if the promise is rejected, they should already
            // have been redirected back to the landing page. However, it may be useful for future debugging, and
            // so we leave it.
            $scope.lxChatRoomOuterCtrl.userSuccessfullyEnteredRoom  = reason;
        });

        $scope.userName = lxAppWideConstantsService.userName;
        $scope.roomName = lxUseChatRoomConstantsService.roomName;


    })

    .controller('lxMainVideoCtrl', function ($scope, lxUseChatRoomConstantsService) {

        $scope.accessCameraAndMicrophoneObject = {
            // modalIsShown will contain the templateUrl for each modal that is currently open. Note that while only
            // a single modal should be shown at once, due to the asynchronous callback nature of the .close() function,
            // we cannot guarantee that the current modal is closed before a new one is opened.
            // This variable should be used as follows:
            // accessCameraAndMicrophoneObject.modalsCurrentlyShown[modal-index#] = templateUrl (where template Url is unique
            // for each modal).
            modalsCurrentlyShown : []
        };

        $scope.remoteVideoObject = {
            remoteVideoElem : undefined, // set in lxVideoElementDirective
            remoteVideoWrapper : undefined // set in lxHdVideoWrapperDirective

        };

        $scope.localVideoObject = {
            localVideoElem :  undefined,  // set in lxVideoElementDirective
            localVideoWrapper : undefined, // set in lxHdVideoWrapperDirective
            miniVideoElemInsideRemoteHd: undefined, //To be set in lxMiniVideoTemplateDirective to .cl-mini-video-element in HD element
            miniVideoElemInsideRemoteAscii: undefined, // To be set in lxMiniVideoTemplateDirective to .cl-mini-video-element in Ascii element
            isVideoMuted : false,
            isAudioMuted : false
        };

        $scope.videoSignalingObject = {
            /*
            We currently only modify the video stream transmission to hdVideo if both the local and remote users
            agree to exchange hdVideo. Therefore, it is necessary to do some handshaking before enabling hdVideo.
            The variables in this object keep track of the handshaking and current video transmission status.
             */

            // localHasSelectedVideoType this reflects the value of the video selection button that the user has
            // clicked on. This is used for highlighting the button that the user has currently selected.
            localHasSelectedVideoType : null,  // null, 'ASCII Video', 'HD Video'.

            // localIsRequestingVideoType is almost the same as localHasSelectedVideoType and when the user initially
            // presses the videoType button, both values will be set to the same value.
            // However, localIsRequestingVideoType is the value that will
            // be watched for changes and that is monitored throughout the video-type-preference code. The difference between
            // localIsRequestingVideoType and localHasSelectedVideoType is that localIsRequestingVideoType (this
            // variable) will not be updated based on feedback from from the remote user such as rejection of a request,
            // while localHasSelectedVideoType will always be updated to reflect the most up-to-date status of the
            // signaling between the local and remote user. This is necessary to prevent our watchers from executing
            // after receiving a rejection of a request to modify the videoType from a remote client.
            localIsRequestingVideoType: null,

            // localIsSendingVideoType will be updated after the remote user has agreed to exchange the new video type and once
            // the video transmission has started (ie. when lxPeerService.addLocalVideoStream is executed)
            localIsSendingVideoType : null,  // null, 'ASCII Video', 'HD Video'

            localUserAccessCameraAndMicrophoneStatus : 'requestNotMade', // 'requestNotMade', 'waitingForResponse', 'allowAccess', 'denyAccess'

            // Once the remote user has joined the room, this will be modified to reflect their userId
            remoteUserId : null,

            // if the local user requests the remote user to change the video type, we track the remote response
            // so that we can give the local user feedback.
            // The value will be set in onChannelMessage.
            remoteVideoSignalingStatus : {
                settingsType: null,  // will be set to null, 'requestVideoType', 'acceptVideoType', or 'denyVideoType'
                videoType: null      // null, 'ASCII Video', 'HD Video'
            },

             /* remoteIsSendingVideoType: The type of video that is being received from the remote User.
             In the case of hdVideo, this will be updated  once the local user starts to receive a video stream from the remote user
             (ie. when lxPeerService.onRemoteStreamAdded is called). In the case of asciiVideo, this will be updated once
             we have received confirmation from the remote user.
             */
            remoteIsSendingVideoType : null,


            // videoSignalingStatusForUserFeedback indicates what message/status the user should be shown about
            // the current video type requested/allowed/waiting for/etc.
            videoSignalingStatusForUserFeedback : null,

            // The following is a flag that is used for debugging - will over-ride ng-show directives on the video
            // windows to show any window that has this flag on it when it is set to true.
            debugShowAllVideoWindows : false
        };

        // setLocalVideoType is called directly from the html, and so it must be placed on the $scope.
        $scope.setLocalVideoType = function(localHasSelectedVideoType) {
            // videoType should be 'HD Video' or 'ASCII Video'
            $scope.videoSignalingObject.localHasSelectedVideoType = localHasSelectedVideoType;
            $scope.videoSignalingObject.localIsRequestingVideoType = localHasSelectedVideoType;
        };

        $scope.myUsername = lxUseChatRoomConstantsService.myUsername;
    })
    .controller('lxVideoNegotiationCtrl', function ($scope, lxVideoSettingsNegotiationService) {
        // This controller is used for wrapping around the lxVideoSettingsNegotiationDirective which may appear
        // in several locations. By wrapping these invocations, we allow common code that is used by multiple
        // copies of the directive to be easily invoked only a single time.
        lxVideoSettingsNegotiationService.watchForVideoSettingsChanges ($scope);
    });