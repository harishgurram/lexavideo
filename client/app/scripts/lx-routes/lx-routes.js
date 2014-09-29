
'use strict';

var lxMainRoutes = angular.module('lxMain.routes', ['ngRoute']);


lxMainRoutes.config(function ($routeProvider, $locationProvider) {
    $locationProvider.html5Mode(true);


    $routeProvider.when('/', {
        templateUrl: function(){
            return '/_lx/lx-templates/lx-landing-page-main.html';
        }
    });

    $routeProvider.when('/:roomName', {
        templateUrl: function(params) {
            return '/_lx/lx-templates/lx-use-chat-room-main.html/' + params.roomName;
        }
    });

    $routeProvider.when('/:roomName/error/:errorString', {
        templateUrl: function(params) {
            return '/_lx/lx-templates/lx-landing-page-main.html/error/' + params.roomName + '/' + params.errorString;
        }
    });

    $routeProvider.otherwise({
        redirectTo: '/'
    });
});


