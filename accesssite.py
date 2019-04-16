#!/usr/bin/python3
# # -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : Access Site
Description          : Class using Qt5 for access site
Date                 : April, 2019
copyright            : (C) 2019 by Luiz Motta
email                : motta.luiz@gmail.com

 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import json

from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal, pyqtSlot,
    QEventLoop,
    QByteArray,
    QUrl
)
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply


class AccessSite(QObject):
    abortReply = pyqtSignal()
    finished = pyqtSignal(dict)
    send_data = pyqtSignal(QByteArray)
    status_download = pyqtSignal(int, int)
    status_erros = pyqtSignal(list)
  
    ErrorCodeAttribute = {
        10:  'Canceled request',
        400: 'Bad request syntax',
        401: 'Unauthorized',
        402: 'Payment required',
        403: 'Forbidden',
        404: 'Not found',
        500: 'Internal error',
        501: 'Not implemented',
        502: 'Bad Gateway'  
    }

    def __init__(self):
        super().__init__()
        self.isKill = None
        self.triedAuthentication = None
        self.nam = QNetworkAccessManager(self)
        self._connect()
        # Input by self.run
        self.credential = None

    def _connect(self, isConnect=True):
        ss = [
            { 'signal': self.nam.finished, 'slot': self.replyFinished },
            { 'signal': self.nam.authenticationRequired, 'slot': self.authenticationRequired }
        ]
        if isConnect:
            for item in ss:
                item['signal'].connect( item['slot'] )  
        else:
            for item in ss:
                item['signal'].disconnect( item['slot'] )

    def _connectReply(self, reply, isConnect=True):
        ss = [
            { 'signal': reply.readyRead, 'slot': self.readyRead },
            { 'signal': reply.sslErrors, 'slot': self.sslErrors }
        ]
        if isConnect:
            if not self.responseAllFinished:
                reply.downloadProgress.connect( self.downloadProgress )
            for item in ss:
                item['signal'].connect( item['slot'] )  
        else:
            if not self.responseAllFinished:
                reply.downloadProgress.disconnect( self.downloadProgress )
            for item in ss:
                item['signal'].disconnect( item['slot'] )

    def _closeReply(self, reply):
        if not self.responseAllFinished:
            self._connectReply( reply, False )
            self.nam.finished.disconnect( self.replyFinished ) # reply.close() call replyFinished
        reply.close()
        if not self.responseAllFinished:
            self.nam.finished.connect( self.replyFinished )
        reply.deleteLater()

    def _redirectionReply(self, reply, url):
        self._closeReply( reply )
        if url.isRelative():
            url = url.resolved( url )
        request = QNetworkRequest( url )
        reply = self.nam.get( request )
        if reply is None:
            response = { 'isOk': False, 'message': "Netwok error", 'errorCode': -1 }
            self.finished.emit( response )
            return
        if not self.responseAllFinished:
            self._connectReply( reply )

    def _emitErrorCodeAttribute(self, code, reply):
        msg = 'Error network' if not code in self.ErrorCodeAttribute.keys() else AccessSite.ErrorCodeAttribute[ code ]
        response = { 'isOk': False, 'message': msg, 'errorCode': code }
        self._closeReply( reply )
        self.finished.emit( response )

    def _checkRedirectionAttribute(self, reply):
        urlRedir = reply.attribute( QNetworkRequest.RedirectionTargetAttribute )
        if not urlRedir is None and urlRedir != reply.url():
            self._redirectionReply( reply, urlRedir )
            return { 'isOk': True }
        codeAttribute = reply.attribute( QNetworkRequest.HttpStatusCodeAttribute )
        if not ( 200 <= codeAttribute <= 299 ):
            self._emitErrorCodeAttribute( codeAttribute, reply )
            return  { 'isOk': False }
        return { 'isOk': True }

    def _clearResponse(self, response):
        if 'data' in response:
            response['data'].clear()
            del response[ 'data' ]
        if 'statusRequest' in response:
            del response['statusRequest']
        if response['isOk']:
            if 'errorCode' in response:
                del response['errorCode']

    def _run(self, url, credential=None, responseAllFinished=True, json_request=None):
        self.isKill, self.triedAuthentication = False, False
        if credential is None:
            credential = {'user': '', 'password': ''}
        self.credential, self.responseAllFinished = credential, responseAllFinished
        req = QNetworkRequest( url )
        if json_request is None:
            reply = self.nam.get( req )
        else:
            req.setHeader( QNetworkRequest.ContentTypeHeader, "application/json" )
            data = QByteArray()
            data.append( json.dumps( json_request ) )
            reply = self.nam.post( req, data )
        if reply is None:
            response = { 'isOk': False, 'message': "Network error", 'errorCode': -1 }
            self.finished.emit( response )
            return
        self.abortReply.connect( reply.abort )
        if not responseAllFinished:
            self._connectReply( reply )

    def requestUrl(self, paramsAccess, addFinishedResponse, setFinished):
        @pyqtSlot(dict)
        def finished( response):
            loop.quit()
            self.finished.disconnect( finished )
            if 'notResponseAllFinished' in paramsAccess:
                self.send_data.disconnect( paramsAccess['notResponseAllFinished']['writePackageImage'] )
                self.status_download.disconnect( paramsAccess['notResponseAllFinished']['progressPackageImage'] )
            response = addFinishedResponse( response )
            if response['isOk']:
                self._clearResponse( response )
            setFinished( response )
        
        loop = QEventLoop()
        self.finished.connect( finished )
        credential = None if not 'credential' in paramsAccess else paramsAccess['credential']
        responseAllFinished = True
        if 'notResponseAllFinished' in paramsAccess:
            responseAllFinished = False
            self.send_data.connect( paramsAccess['notResponseAllFinished']['writePackageImage'] )
            self.status_download.connect( paramsAccess['notResponseAllFinished']['progressPackageImage'] )     
        json_request = None if not 'json_request' in paramsAccess else paramsAccess['json_request']
        self._run( paramsAccess['url'], credential, responseAllFinished, json_request )
        loop.exec_()

    def isHostLive(self, url, setFinished):
        def addFinishedResponse(response):
            if response['isOk']:
                return response
            else:
                if response['errorCode'] == QNetworkReply.HostNotFoundError:
                    response['message'] = "{}\nURL = {}".format( response['message'], self.urlGeoserver )
                else:
                    response['isOk'] = True
            return response

        p = { 'url': QUrl( url ) }
        self.requestUrl( p, addFinishedResponse, setFinished )

    def getThumbnail(self, url, setFinished):
        def addFinishedResponse(response):
            if not response['isOk']:
                return response
            if 'data' in response: # The user can quickly change a item
                pixmap = QPixmap()
                if not pixmap.loadFromData( response['data'] ):
                    response['isOk'] = False
                    response['message'] = 'Invalid image from Mapbiomas server'
                else:
                    response['thumbnail'] = pixmap
            return response

        p = { 'url': QUrl( url ) }
        self.requestUrl( p, addFinishedResponse, setFinished )

    @pyqtSlot('QNetworkReply*')
    def replyFinished(self, reply) :
        if self.isKill:
            self._emitErrorCodeAttribute(10, reply )
            return
        if reply.error() != QNetworkReply.NoError:
            response = { 'isOk': False, 'message': reply.errorString(), 'errorCode': reply.error() }
            self._closeReply( reply )
            self.finished.emit( response )
            return
        r = self._checkRedirectionAttribute( reply )
        if not r['isOk']:
            return

        statusRequest = {
            'contentTypeHeader': reply.header( QNetworkRequest.ContentTypeHeader ),
            'lastModifiedHeader': reply.header( QNetworkRequest.LastModifiedHeader ),
            'contentLengthHeader': reply.header( QNetworkRequest.ContentLengthHeader ),
            'statusCodeAttribute': reply.attribute( QNetworkRequest.HttpStatusCodeAttribute ),
            'reasonPhraseAttribute': reply.attribute( QNetworkRequest.HttpReasonPhraseAttribute )
        }
        response = { 'isOk': True, 'statusRequest': statusRequest }
        if self.responseAllFinished:
            response['data'] = reply.readAll()
        self._closeReply( reply )
        self.finished.emit( response )

    @pyqtSlot('QNetworkReply*', 'QAuthenticator*')
    def authenticationRequired (self, reply, authenticator):
        if not self.triedAuthentication: 
            authenticator.setUser( self.credential['user'] ) 
            authenticator.setPassword( self.credential['password'] )
            self.triedAuthentication = True
        else:
            self._emitErrorCodeAttribute(401, reply )

    @pyqtSlot()
    def readyRead(self):
        reply = self.sender()
        if self.isKill:
            self._emitErrorCodeAttribute(10, reply )
            return
        r = self._checkRedirectionAttribute( reply )
        if not r['isOk']:
            return
        if not reply.isOpen():
            reply.open( QNetworkReply.ReadOnly )
        data = reply.readAll()
        if data is None:
            return
        self.send_data.emit( data )

    @pyqtSlot('qint64', 'qint64')
    def downloadProgress(self, bytesReceived, bytesTotal):
        reply = self.sender()
        if self.isKill:
            self._emitErrorCodeAttribute(10, reply )
        else:
            self.status_download.emit( bytesReceived, bytesTotal )

    @pyqtSlot('QList<QSslError>')
    def sslErrors(self, errors):
        reply = self.sender()
        lstErros = map( lambda e: e.errorString(), errors )
        self.status_erros.emit( lstErros )
        reply.ignoreSslErrors()

    @staticmethod
    def loadJsonData(response):
        data = response['data'].data()
        sdata = str(data, encoding='utf-8')
        return json.loads( sdata )