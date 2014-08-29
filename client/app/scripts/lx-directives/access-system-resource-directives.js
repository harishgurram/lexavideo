/**
 * Created by alexandermarquardt on 2014-08-27.
 */
'use strict';
/* global $ */

var lxAccessSystemResources = angular.module('lxAccessSystemResources.directives', []);

lxAccessSystemResources.directive('lxAccessCameraAndMicrophoneDirective', function($timeout, $animate,
                                                                              serverConstantsService, callService,
                                                                              mediaService, lxCheckCompatibilityService,
                                                                              lxModalSupportService) {

    var timerId;

    // initially define the watchers as dummy functions, so that they can be "de-registered" even if they were not
    // initially called.
    var watchLocalUserAccessCameraAndMicrophoneStatus1 = function() {},
        watchLocalUserAccessCameraAndMicrophoneStatus2 = function() {},
        watchLocalUserAccessCameraAndMicrophoneStatus3 = function() {},
        watchForModalClosed = function() {};


    var askForPermissionToCameraAndMicrophone = function(localVideoElem, videoSignalingObject) {
        if (serverConstantsService.mediaConstraints.audio === false &&
            serverConstantsService.mediaConstraints.video === false) {
            callService.hasAudioOrVideoMediaConstraints = false;
        } else {
            callService.hasAudioOrVideoMediaConstraints = true;
            mediaService.doGetUserMedia(localVideoElem, videoSignalingObject);
        }
    };

    var showArrowPointingToAcceptButton = function(scope, elem, videoSignalingObject) {
        var arrowWrapperClass = '';
        var timeoutInMilliseconds = 0;
        var wrapperElement;

        if ($.browser.name === 'chrome') {
            if ($.browser.platform === 'mac') {
                arrowWrapperClass = 'cl-arrow-wrapper-mac-chrome';
            }
            else if ($.browser.desktop) {
                arrowWrapperClass = 'cl-arrow-wrapper-desktop-default-chrome';
            }
        }
        if ($.browser.name === 'mozilla') {

            if ($.browser.desktop) {
                // only show the arrow on desktops, since it appears that on mobile devices there is no
                // camera symbol in the URL to point the user to.
                arrowWrapperClass = 'cl-arrow-wrapper-mozilla';
            }

            // Since mozilla/firefox has a popup as opposed to a banner, we wait longer before showing the arrow.
            // If the user has accidentally clicked somewhere on the screen, then they need to be directed to the
            // camera icon to the left of where the URL is displayed.
            timeoutInMilliseconds = 0;
        }

        if ($.browser.name === 'opera') {
            // no arrow required, since opera has a popup window that is quite obvious and that does not get
            // accidentaly hidden as may happen in firefox.
        }

        if (arrowWrapperClass !== '') {
            // only show the arrow if the arrowWrapperClass has been defined -- if it has not been defined, then
            // no arrow should be shown.
            elem.append('<div class="cl-arrow '+ arrowWrapperClass + '"><span class="icon-lx-arrow-up"></span></div>');
            wrapperElement = angular.element(elem).find('.' + arrowWrapperClass);

            $timeout(function() {
                // wait a second before starting to show the arrow. This gives time for the initial status to correctly propagate.
                // This is delay allows us to detect 'denyAccess' status if the user has previously denied camera access
                // and to therefore start the pointer at the correct horizontal position.

                if (videoSignalingObject.localUserAccessCameraAndMicrophoneStatus === 'denyAccess') {
                    wrapperElement.addClass('camera-access-was-denied');
                }

                if (videoSignalingObject.localUserAccessCameraAndMicrophoneStatus !== 'allowAccess') {
                    var timeoutFn = function() {
                        timerId = $timeout(function() {
                            if (wrapperElement.hasClass('cl-show-arrow')) {
                                wrapperElement.removeClass('cl-show-arrow');
                                timeoutInMilliseconds = 3000;
                            } else {
                                // the arrow is now shown, leave it there for a while
                                $animate.addClass(wrapperElement, 'cl-show-arrow');
                                timeoutInMilliseconds = 15000;
                            }
                            timeoutFn();
                        }, timeoutInMilliseconds);
                    };
                    timeoutFn();
                }
            }, 1000);


            watchLocalUserAccessCameraAndMicrophoneStatus1 =
                scope.$watch('videoSignalingObject.localUserAccessCameraAndMicrophoneStatus', function() {
                    if (videoSignalingObject.localUserAccessCameraAndMicrophoneStatus === 'denyAccess') {
                        // monitor to see if user denies access to the camera, and if this happens then
                        // move the arrow over to point to the camera icon instead of to the allow button.
                        if ($.browser.name === 'chrome') {
                            // across all desktop platforms, the camera icon appears to be in the same location
                            if ($.browser.desktop) {
                                wrapperElement = angular.element(elem).find('.' + arrowWrapperClass);
                                wrapperElement.addClass('camera-access-was-denied');
                            }
                        }
                    }
                });


        }
    };

    var showNewModalAndCloseOldModal = function(scope, elem, htmlTemplate, currentlyDisplayedModalInstance, windowClass) {


        if (currentlyDisplayedModalInstance) {
            // if there is already a modal open, close it so that we don't have them stacking on top of each other.
            currentlyDisplayedModalInstance.close();
        }

        currentlyDisplayedModalInstance =  lxModalSupportService.showCameraAndMicrophoneModalWindow(scope, htmlTemplate, windowClass);
        return currentlyDisplayedModalInstance;
    };


    var showModalInstructionsForCameraAndMicrophone = function(scope, elem) {

        var currentlyDisplayedModalInstance;
        var windowClass = '';

        if (lxCheckCompatibilityService.userDeviceBrowserAndVersionSupported) {
            // If the users's device and browser support webRTC, then show them instructions on how to access their
            // camera and microphone. Otherwise, they should already have been shown instructions from
            // lx-check-compatibility-directives, which would have told them what they need to do to access the site.

            watchLocalUserAccessCameraAndMicrophoneStatus3 =
                scope.$watch('videoSignalingObject.localUserAccessCameraAndMicrophoneStatus', function(newStatus) {

                    if (newStatus === 'allowAccess') {
                        currentlyDisplayedModalInstance.close();
                    }


                    if ($.browser.name === 'chrome') {
                        if (newStatus === 'denyAccess') {
                            if ($.browser.desktop) {
                                currentlyDisplayedModalInstance = showNewModalAndCloseOldModal(scope, elem,
                                    'lx-template-cache/chrome-desktop-access-camera-previously-denied-modal.html',
                                    currentlyDisplayedModalInstance, windowClass);
                            }
                            else {
                                // mobile device
                            }
                        }
                        else  if (newStatus === 'waitingForResponse') {
                            if ($.browser.platform === 'mac') {
                                currentlyDisplayedModalInstance = showNewModalAndCloseOldModal(scope, elem,
                                    'lx-template-cache/chrome-mac-access-camera-modal.html',
                                    currentlyDisplayedModalInstance, windowClass);
                            }
                            else if ($.browser.desktop) {
                                // windows/linux desktop devices. Chrome appears to have the same layout in both.
                                currentlyDisplayedModalInstance = showNewModalAndCloseOldModal(scope, elem,
                                    'lx-template-cache/chrome-desktop-access-camera-modal.html',
                                    currentlyDisplayedModalInstance, windowClass);
                            }
                            else {
                                // should be mobile
                            }
                        }
                    }
                    if ($.browser.name === 'mozilla') {

                        if ($.browser.desktop) {
                            windowClass = 'cl-firefox-camera-access-modal-override';
                            currentlyDisplayedModalInstance = showNewModalAndCloseOldModal(scope, elem,
                                'lx-template-cache/mozilla-desktop-access-camera-modal.html',
                                currentlyDisplayedModalInstance, windowClass);
                        }
                    }

                    if ($.browser.name === 'opera') {

                    }
                });
        }
    };

    var removeArrowAndAssociatedWatchers = function(elem) {
        var arrowElement = angular.element(elem).find('.cl-arrow');
        arrowElement.addClass('ng-hide');

        // cancel timer that is no longer required
        $timeout.cancel(timerId);

        // de-register the watchers that are no longer required
        watchLocalUserAccessCameraAndMicrophoneStatus1();
        watchLocalUserAccessCameraAndMicrophoneStatus2();
        watchLocalUserAccessCameraAndMicrophoneStatus3();
        watchForModalClosed();
    };

    var checkIfAModalIsShown = function(scope) {
        return function() {
            for (var key in scope.accessCameraAndMicrophoneObject.modalIsShown) {
                if (scope.accessCameraAndMicrophoneObject.modalIsShown.hasOwnProperty(key)){
                    var value = scope.accessCameraAndMicrophoneObject.modalIsShown[key];
                    if (value) {
                        return true;
                    }
                }
            }
            return false;
        };
    };

    return {
        restrict: 'A',
        link: function(scope, elem) {
            var videoSignalingObject = scope.videoSignalingObject;
            var localVideoElem = scope.localVideoObject.localVideoElem;

            askForPermissionToCameraAndMicrophone(localVideoElem, videoSignalingObject);
            showModalInstructionsForCameraAndMicrophone(scope, elem);

            watchForModalClosed =
                scope.$watch(checkIfAModalIsShown(scope), function(aModalIsOpen) {
                    if (aModalIsOpen) {
                        showArrowPointingToAcceptButton(scope, elem, videoSignalingObject);
                    } else {
                        removeArrowAndAssociatedWatchers(elem, videoSignalingObject);
                    }
                });

            watchLocalUserAccessCameraAndMicrophoneStatus2 =
                scope.$watch('videoSignalingObject.localUserAccessCameraAndMicrophoneStatus', function() {
                    if (videoSignalingObject.localUserAccessCameraAndMicrophoneStatus === 'allowAccess') {
                        removeArrowAndAssociatedWatchers(elem);
                    }
                });
        }
    };
});
