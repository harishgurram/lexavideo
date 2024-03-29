/*
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
*/

'use strict';
/* global $ */

angular.module('lxCheckCompatibility.services', [])

    // Provides flags that are used for checking if the current device/browser is supported.
    .factory('lxCheckCompatibilityService', function () {


        function checkIfBrowserVersionIsSupported () {

            /* Supported browsers and OSes
             ***********************************
             * Information from general internet search:
             * Firefox: windows, mac, linux, android : Since version 24. Current version is 31 (all platforms).
             * Chrome: desktop: 23, android: 28. Current version: 36 (all platforms)
             * Opera: Android 20
             ***********************************
             * Information from caniuse.com -- this seems to be too conservative.
             * Firefox: 30
             * Chrome desktop: 27
             * Chrome Android: 36
             * Opera (not mini): 23 - is incorrect - have installed 22 on android and it has webRTC (23 not available on android yet)
             ************************************
             * We use the information from the general internet search as a minimum version number, but if possible we select the
             * current version minus a few revisions so that users are not forced to upgrade just to use webRtc
             */


            var mozillaRequiredVersion = 28; // firefox
            var chromeRequiredVersion = 30;
            var operaRequiredVersion = 20;

            if ($.browser.mozilla && $.browser.versionNumber <  mozillaRequiredVersion ||
                $.browser.chrome && $.browser.versionNumber < chromeRequiredVersion ||
                $.browser.opera && $.browser.versionNumber < operaRequiredVersion) {
                // The users browser is out of date and needs to be updated before they can access the website.
                return false;
            } else {
                return true;
            }

        }


        var isIosDevice = $.browser.ipad || $.browser.iphone;
        var isSupportedBrowser = $.browser.mozilla || $.browser.chrome || $.browser.opera;
        var browserVersionIsSupported = checkIfBrowserVersionIsSupported();
        var userDeviceBrowserAndVersionSupported = !isIosDevice && isSupportedBrowser && browserVersionIsSupported;



        return {
            isIosDevice : isIosDevice,
            isSupportedBrowser : isSupportedBrowser,
            browserVersionIsSupported : browserVersionIsSupported,
            userDeviceBrowserAndVersionSupported: userDeviceBrowserAndVersionSupported
        };
    });