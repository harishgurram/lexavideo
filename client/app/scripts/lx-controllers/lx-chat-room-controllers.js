/**
 * Created by alexandermarquardt on 2014-07-08.
 */
'use strict';

/* global $ */

angular.module('LxChatRoom.controllers', [])

    // *** WARNING ***
    // *** WARNING *** because we are "faking" the chat panel views, LxChatMainController does not wrap the chat panels
    // *** WARNING ***

    .controller('LxChatMainController', function(
        $location,
        $routeParams,
        $log,
        $scope,
        $timeout,
        lxAuthenticationHelper,
        lxHttpChannelService,
        lxJs,
        lxChatRoomMembersService
        ) {

        $scope.lxMainCtrlDataObj.currentView = 'LxChatMainView';
        $scope.mainMenuObject.showMainMenu = false;

        // we wait for the ng-view animation to end before we show the video elements. This
        // is necessary because the video interferes with the animations.
        // Note: the "one" handler is unbound after it's first invocation, which is exactly what we want.
        $scope.videoStateInfoObject.enableShowVideoElements = false;
        $('.cl-ng-view').one('animationend webkitAnimationEnd oAnimationEnd MSAnimationEnd', function(){
            $scope.$apply(function() {
                $scope.videoStateInfoObject.enableShowVideoElements = true;
            });
        });

        // We need to wait for the clientId to be set before we can enter the client into the room.
        // Notice that we don't ever kill this watcher - this is intentional because there may be cases
        // where the user session expires on the server, which causes a new clientId to be allocated which
        // requires that the client be re-added to the room.
        var watchClientIdBeforeHandleRoomNameFromUrl = $scope.$watch(
            function() {
                return $scope.lxMainCtrlDataObj.clientId;
            },
            function(clientId) {
                if (clientId) {
                    lxChatRoomMembersService.handleChatRoomNameFromUrl($scope);
                }
            }
        );
    })

    .controller('LxVideoController',
    function (
        $log,
        $scope,
        lxAccessCameraAndMicrophoneService,
        lxCallService,
        lxCheckIfSystemSupportsWebRtcService,
        lxVideoService,
        lxVideoParamsService) {

        $scope.accessCameraAndMicrophoneObject = {
            // modalIsShown will contain the templateUrl for each modal that is currently open. Note that while only
            // a single modal should be shown at once, due to the asynchronous callback nature of the .close() function,
            // we cannot guarantee that the current modal is closed before a new one is opened.
            // This variable should be used as follows:
            // accessCameraAndMicrophoneObject.modalsCurrentlyShown[modal-index#] = templateUrl (where template Url is unique
            // for each modal).
            modalsCurrentlyShown: []
        };

        $scope.videoDisplaySelection = {
            // currentlySelectedVideoElementClientId will either be remoteClientId or the string 'localVideoElement'
            currentlySelectedVideoElementClientId: 'localVideoElement'
        };


        $scope.showCameraAndMicrophoneInstructions = function() {

            // checkBrowserVersionToSeeIfGetUserMediaSupported will show a modal to the user if their browser/device is
            // not supported. If it is supported, then it will return true and the prompt for access to camera and mic
            // will be presented.
            if (lxCheckIfSystemSupportsWebRtcService.checkBrowserVersionToSeeIfGetUserMediaSupported($scope)) {
                lxAccessCameraAndMicrophoneService.showModalsAndArrowsForGrantingCameraAndMicrophoneAccess($scope);
            }
        };

        $scope.toggleWebcamMuteInterfaceFn = function() {
            lxCallService.toggleWebcamMute($scope.localVideoObject);
        };

        $scope.toggleMicrophoneMuteInterfaceFn = function() {
            lxCallService.toggleMicrophoneMute($scope.localVideoObject);
        };

        $scope.toggleAudioMuteInterfaceFn = function(remoteClientId) {
            lxCallService.toggleAudioMute($scope.remoteVideoElementsDict[remoteClientId]);
        };

        $scope.myUsername = lxVideoParamsService.myUsername;

        $scope.showVideoElementsAndStartVideoFn = function(localVideoEnabledSetting, remoteClientId) {
            lxVideoService.showVideoElementsAndStartVideoFn($scope, localVideoEnabledSetting, remoteClientId);
        };
    });