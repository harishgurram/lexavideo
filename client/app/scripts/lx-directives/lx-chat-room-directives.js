'use strict';



angular.module('lxChatRoom.directives', [])

    .directive('lxInitializeTurnDirective',
    function(
        $log,
        lxTurnService
        ) {

        return {
            restrict: 'A',
            link: function() {
                try {
                    lxTurnService.maybeRequestTurn();
                }
                catch (e) {
                    e.message = '\n\tError in lxInitializeTurnDirective\n\t' + e.message;
                    $log.error(e);
                    return false;
                }
            }
        };
    })

    // Directive that will control signalling between two users about the type of video that they wish to transmit.
    // (ie. HD Video or Ascii Video)
    .directive('lxVideoNegotiationDirective',
    function (
        lxSelectAndNegotiateVideoTypeService) {


        return {
            restrict: 'A',
            link: function(scope) {
                lxSelectAndNegotiateVideoTypeService.watchForVideoSettingsChanges (scope);
            }
        };
    })


    .directive('lxAccessCameraAndMicrophoneDirective',
    function(
        lxAccessCameraAndMicrophoneService)
    {

        return {
            restrict: 'A',
            link: function(scope) {
                lxAccessCameraAndMicrophoneService.showModalsAndArrowsForGrantingCameraAndMicrophoneAccess(scope);
            }
        };
    })

    .directive('lxShowUnseenMessageCountDirective',
    function(
        lxShowNumMessagesService
        ){

        return {
            restrict: 'A',
            link: function(scope) {

                // If the user is not focused on the current window, and then comes back to look at the current window
                // then the messages shown in the chat panel that is open in the window will be considered to have been
                // viewed, and the message counts will be adjusted accordingly.
                scope.$watch('windowWatcher.isFocused', function() {
                    var chatPanelObject = scope.chatRoomDisplayObject.chatPanelObject;
                    if (chatPanelObject) {
                        lxShowNumMessagesService.stopFlashingTitleAndAdjustCount(scope.trackUnseenMessageCountObject, chatPanelObject);
                        lxShowNumMessagesService.showNumMessagesInDocumentTitle(scope.trackUnseenMessageCountObject);
                    }
                });
            }
        };
    })


    .directive('lxNotificationMenuButtonDirective',
    function(){

        return {
            restrict: 'A',
            template: '' +
                '<span style="white-space: nowrap">' +
                    '<span class="cl-text-size-1_5em" style="vertical-align:middle"' +
                        'ng-class="notificationMenuObject.partialShowNotificationMenuAndGetAttention?\'cl-text-danger cl-text-shadow cl-pulse\': \'\'">' +
                        '<span class="icon-lx-flag"></span>' +
                    '</span>' +
                    '<span ng-if="videoStateInfoObject.numVideoRequestsPendingFromRemoteUsers"' +
                        'ng-class="notificationMenuObject.partialShowNotificationMenuAndGetAttention?\'cl-text-danger\':\'\'"' +
                        'class="bubble bubble-left cl-notification-count-bubble-override"><i></i>' +
                        '{{ videoStateInfoObject.numVideoRequestsPendingFromRemoteUsers }}' +
                    '</span>'+
                '</span>',

            link: function(scope, elem) {

                function applyToggleNotificationMenu(event) {
                    scope.$apply(function() {
                        scope.toggleNotificationMenu(event);
                    });
                }

                elem.on('click', applyToggleNotificationMenu);
                scope.$on('$destroy', function(){elem.off('click', applyToggleNotificationMenu);});

                // if the user gets a new notification then we want to draw attention to the button.
                scope.$watch('videoStateInfoObject.numVideoRequestsPendingFromRemoteUsers', function(numPendingRequests, prevNumPendingRequests) {
                    if (numPendingRequests > 0 && numPendingRequests > prevNumPendingRequests) {
                        // Show the "partial" notification menu, but only if the "full" notification menu is not already
                        // being viewed.
                        if (!scope.notificationMenuObject.showNotificationMenu) {
                            scope.notificationMenuObject.partialShowNotificationMenuAndGetAttention = true;
                        }
                    }

                    if (numPendingRequests === 0) {
                        scope.notificationMenuObject.partialShowNotificationMenuAndGetAttention = false;
                    }
                });
            }
        };
    });