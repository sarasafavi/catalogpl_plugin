# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : QtCore.Qt API for Catalog Planet Labs 
Description          : API for Planet Labs
Date                 : May, 2015
copyright            : (C) 2015 by Luiz Motta
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

import json, datetime

from PyQt4 import QtCore, QtGui, QtNetwork

class AccessSite(QtCore.QObject):

  # Signals
  finished = QtCore.pyqtSignal( dict)
  send_data = QtCore.pyqtSignal(QtCore.QByteArray)
  status_download = QtCore.pyqtSignal(int, int)
  status_erros = QtCore.pyqtSignal(list)
  
  ErrorCodeAttribute = { 
     10: 'Canceled request',
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
    super( AccessSite, self ).__init__()
    self.networkAccess = QtNetwork.QNetworkAccessManager(self)
    self.totalReady = self.reply = self.triedAuthentication = self.isKilled = None
    # Input by self.run
    self.credential = self.responseAllFinished = None

  def run(self, url, credential=None, responseAllFinished=True, json_request=None):
    if credential is None:
      credential = {'user': '', 'password': ''}
    ( self.credential, self.responseAllFinished ) = ( credential, responseAllFinished )
    self._connect()
    self.totalReady = 0
    self.isKilled = False
    request = QtNetwork.QNetworkRequest( url )
    if json_request is None:
      reply = self.networkAccess.get( request )
    else:
      request.setHeader( QtNetwork.QNetworkRequest.ContentTypeHeader, "application/json" )
      data = QtCore.QByteArray( json.dumps( json_request ) )
      reply = self.networkAccess.post( request, data )
    if reply is None:
      response = { 'isOk': False, 'message': "Network error", 'errorCode': -1 }
      self._connect( False )
      self.finished.emit( response )
      return

    self.triedAuthentication = False
    self.reply = reply
    self._connectReply()
  
  def kill(self):
    self.isKilled = True
  
  def isRunning(self):
    return ( not self.reply is None and self.reply.isRunning() )  

  def _connect(self, isConnect=True):
    ss = [
      { 'signal': self.networkAccess.finished, 'slot': self.replyFinished },
      { 'signal': self.networkAccess.authenticationRequired, 'slot': self.authenticationRequired }
    ]
    if isConnect:
      for item in ss:
        item['signal'].connect( item['slot'] )  
    else:
      for item in ss:
        item['signal'].disconnect( item['slot'] )

  def _connectReply(self, isConnect=True):
    ss = [
      { 'signal': self.reply.readyRead, 'slot': self.readyRead },
      { 'signal': self.reply.downloadProgress, 'slot': self.downloadProgress },
      { 'signal': self.reply.sslErrors, 'slot': self.sslErrors }
    ]
    if isConnect:
      for item in ss:
        item['signal'].connect( item['slot'] )  
    else:
      for item in ss:
        item['signal'].disconnect( item['slot'] )

  def _clearConnect(self):
    self._connect( False ) # self.reply.close() -> emit signal self.networkAccess.finished
    self._connectReply( False )
    self.reply.close()
    self.reply.deleteLater();
    del self.reply
    self.reply = None

  def _redirectionReply(self, url):
    self._clearConnect()
    self._connect()
    if url.isRelative():
      url = url.resolved( url )

    request = QtNetwork.QNetworkRequest( url )
    reply = self.networkAccess.get( request )
    if reply is None:
      response = { 'isOk': False, 'message': "Netwok error", 'errorCode': -1 }
      self._connect( False )
      self.finished.emit( response )
      return

    self.reply = reply
    self._connectReply()
    
  def _errorCodeAttribute(self, code):
    msg = 'Error network' if not code in self.ErrorCodeAttribute.keys() else AccessSite.ErrorCodeAttribute[ code ]
    response = { 'isOk': False, 'message': msg, 'errorCode': code }
    self._clearConnect()
    self.finished.emit( response )

  @QtCore.pyqtSlot(QtNetwork.QNetworkReply)
  def replyFinished(self, reply) :
    if self.isKilled:
      self._errorCodeAttribute(10)

    if reply.error() != QtNetwork.QNetworkReply.NoError :
      response = { 'isOk': False, 'message': reply.errorString(), 'errorCode': reply.error() }
      self._clearConnect()
      self.finished.emit( response )
      return

    urlRedir = reply.attribute( QtNetwork.QNetworkRequest.RedirectionTargetAttribute )
    if not urlRedir is None and urlRedir != reply.url():
      self._redirectionReply( urlRedir )
      return

    codeAttribute = reply.attribute( QtNetwork.QNetworkRequest.HttpStatusCodeAttribute )
    if codeAttribute != 200:
      self._errorCodeAttribute( codeAttribute )
      return

    statusRequest = {
      'contentTypeHeader': reply.header( QtNetwork.QNetworkRequest.ContentTypeHeader ),
      'lastModifiedHeader': reply.header( QtNetwork.QNetworkRequest.LastModifiedHeader ),
      'contentLengthHeader': reply.header( QtNetwork.QNetworkRequest.ContentLengthHeader ),
      'statusCodeAttribute': reply.attribute( QtNetwork.QNetworkRequest.HttpStatusCodeAttribute ),
      'reasonPhraseAttribute': reply.attribute( QtNetwork.QNetworkRequest.HttpReasonPhraseAttribute )
    }
    response = { 'isOk': True, 'statusRequest': statusRequest }
    if self.responseAllFinished:
      response[ 'data' ] = reply.readAll()
    else:
      response[ 'totalReady' ] = self.totalReady

    self._clearConnect()
    self.finished.emit( response )

  @QtCore.pyqtSlot(QtNetwork.QNetworkReply, QtNetwork.QAuthenticator)
  def authenticationRequired (self, reply, authenticator):
    if not self.triedAuthentication: 
      authenticator.setUser( self.credential['user'] ) 
      authenticator.setPassword( self.credential['password'] )
      self.triedAuthentication = True
    else:
      self._errorCodeAttribute( 401 )

  @QtCore.pyqtSlot()
  def readyRead(self):
    if self.isKilled:
      self._errorCodeAttribute(10)
      return

    if self.responseAllFinished:
      return

    urlRedir = self.reply.attribute( QtNetwork.QNetworkRequest.RedirectionTargetAttribute )
    if not urlRedir is None and urlRedir != self.reply.url():
      self._redirectionReply( urlRedir )
      return

    codeAttribute = self.reply.attribute( QtNetwork.QNetworkRequest.HttpStatusCodeAttribute )
    if codeAttribute != 200:
      self._errorCodeAttribute( codeAttribute )
      return

    data = self.reply.readAll()
    if data is None:
      return
    self.totalReady += len ( data )
    self.send_data.emit( data )

  @QtCore.pyqtSlot(int, int)
  def downloadProgress(self, bytesReceived, bytesTotal):
    if self.isKilled:
      self._errorCodeAttribute(10)
    else:
      self.status_download.emit( bytesReceived, bytesTotal )

  @QtCore.pyqtSlot( list )
  def sslErrors(self, errors):
    lstErros = map( lambda e: e.errorString(), errors )
    self.status_erros.emit( lstErros )
    self.reply.ignoreSslErrors()


class API_PlanetLabs(QtCore.QObject):

  errorCodeLimitOK = (201, 207) # https://en.wikipedia.org/wiki/List_of_HTTP_status_codes (2107-09-30)
  errorCodeDownloads =  { # Planet DOC (2107-09-30)
    299: 'Download quota has been exceeded',
    429: 'Request has been denied due to exceeding rate limits.'
  } 
  validKey = None
  urlRoot = "https://api.planet.com"
  urlQuickSearch = "https://api.planet.com/data/v1/quick-search"
  urlThumbnail = "https://tiles.planet.com/data/v1/item-types/{item_type}/items/{item_id}/thumb"
  urlTMS = "https://tiles.planet.com/data/v1/{item_type}/{item_id}/{{z}}/{{x}}/{{y}}.png"
  urlAssets = "https://api.planet.com/data/v1/item-types/{item_type}/items/{item_id}/assets" 

  def __init__(self):
    super( API_PlanetLabs, self ).__init__()
    self.access = AccessSite()
    self.currentUrl = None

  def _clearResponse(self, response):
    if response.has_key('data'):
      response['data'].clear()
      del response[ 'data' ]
    del response[ 'statusRequest' ]

  def kill(self):
    self.access.kill()

  def isRunning(self):
    return self.access.isRunning()

  def isHostLive(self, setFinished):
    @QtCore.pyqtSlot(dict)
    def finished( response):
      self.access.finished.disconnect( finished )
      if response['isOk']:
        response[ 'isHostLive' ] = True
        self._clearResponse( response )
      else:
        if response['errorCode'] == QtNetwork.QNetworkReply.HostNotFoundError:
          response[ 'isHostLive' ] = False
          response[ 'message' ] += "\nURL = %s" % API_PlanetLabs.urlRoot
        else:
          response[ 'isHostLive' ] = True

      setFinished( response )

    self.currentUrl = API_PlanetLabs.urlRoot
    url = QtCore.QUrl( self.currentUrl )
    self.access.finished.connect( finished )
    credential = { 'user': '', 'password': ''}
    self.access.run( url, credential )

  def setKey(self, key, setFinished):
    @QtCore.pyqtSlot(dict)
    def finished( response):
      self.access.finished.disconnect( finished )
      if response['isOk']:
        API_PlanetLabs.validKey = key
        self._clearResponse( response )

      setFinished( response )

    self.currentUrl = API_PlanetLabs.urlRoot
    url = QtCore.QUrl( self.currentUrl )
    self.access.finished.connect( finished )
    credential = { 'user': key, 'password': ''}
    self.access.run( url, credential )

  def getUrlScenes(self, json_request, setFinished):
    @QtCore.pyqtSlot(dict)
    def finished( response):
      self.access.finished.disconnect( finished )
      if response[ 'isOk' ]:
        data = json.loads( str( response['data'] ) )
        response[ 'url_scenes' ] = data['_links']['_self']
        response['total'] = len( data['features'] )
        
        data.clear()
        self._clearResponse( response )

      setFinished( response )

    self.currentUrl = API_PlanetLabs.urlQuickSearch
    url = QtCore.QUrl( self.currentUrl )
    self.access.finished.connect( finished )
    credential = { 'user': API_PlanetLabs.validKey, 'password': ''}
    self.access.run( url, credential, json_request=json_request )

  def getScenes(self, url, setFinished):
    @QtCore.pyqtSlot(dict)
    def finished( response):
      self.access.finished.disconnect( finished )
      if response[ 'isOk' ]:
        data = json.loads( str( response[ 'data' ] ) )
        response[ 'url' ] = data[ '_links' ][ '_next' ]
        response[ 'scenes' ] = data[ 'features' ]
        self._clearResponse( response )

      setFinished( response )

    self.currentUrl = url
    url = QtCore.QUrl.fromEncoded( url )
    self.access.finished.connect( finished )
    credential = { 'user': API_PlanetLabs.validKey, 'password': '' }
    self.access.run( url, credential )

  def getAssetsStatus(self, item_type, item_id, setFinished):
    @QtCore.pyqtSlot(dict)
    def finished( response):
      def setStatus(asset):
        def getDateTimeFormat(d):
          dt = datetime.datetime.strptime( d, "%Y-%m-%dT%H:%M:%S.%f")
          return dt.strftime( formatDateTime )

        key = "a_{0}".format( asset )
        response['assets_status'][ key ] = {}
        r = response['assets_status'][ key ]
        if not data.has_key( asset ):
          r['status'] = "*None*"
          return
        if data[ asset ].has_key('status'):
          r['status'] = data[ asset ]['status']
        if data[ asset ].has_key('_permissions'):
          permissions = ",".join( data[ asset ]['_permissions'])
          r['permissions'] = permissions
        if data[ asset ].has_key('expires_at'):
          r['expires_at'] = getDateTimeFormat( data[ asset ]['expires_at'] )
        if data[ asset ].has_key('_links'):
          if data[ asset ]['_links'].has_key('activate'):
            r['activate'] = data[ asset ]['_links']['activate']
        if data[ asset ].has_key('location'):
          r['location'] = data[ asset ]['location']

      self.access.finished.disconnect( finished )
      if response[ 'isOk' ]:
        formatDateTime = '%Y-%m-%d %H:%M:%S'
        date_time = datetime.datetime.now().strftime( formatDateTime )
        response['assets_status'] = {
          'date_calculate': date_time,
          'url': self.currentUrl
        }
        data = json.loads( str( response[ 'data' ] ) )
        setStatus('analytic')
        setStatus('udm') 
        self._clearResponse( response )

      setFinished( response )

    url = API_PlanetLabs.urlAssets.format(item_type=item_type, item_id=item_id)
    self.currentUrl = url
    url = QtCore.QUrl.fromEncoded( url )

    self.access.finished.connect( finished )
    credential = { 'user': API_PlanetLabs.validKey, 'password': ''}
    self.access.run( url, credential )

  def getThumbnail(self, item_id, item_type, setFinished):
    @QtCore.pyqtSlot(dict)
    def finished( response ):
      self.access.finished.disconnect( finished )
      if response['isOk']:
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData( response[ 'data' ] )
        response[ 'pixmap' ] = pixmap
        self._clearResponse( response )

      setFinished( response )

    url = API_PlanetLabs.urlThumbnail.format( item_type=item_type, item_id=item_id )
    self.currentUrl = url
    url = QtCore.QUrl( url )
    self.access.finished.connect( finished )
    credential = { 'user': API_PlanetLabs.validKey, 'password': ''}
    self.access.run( url, credential )

  def activeAsset(self, url, setFinished):
    @QtCore.pyqtSlot(dict)
    def finished( response ):
      self.access.finished.disconnect( finished )
      if response['isOk']:
        self._clearResponse( response )
      setFinished( response ) # response[ 'totalReady' ]
      
    url = QtCore.QUrl.fromEncoded( url )
    url = QtCore.QUrl( url )
    self.access.finished.connect( finished )
    credential = { 'user': API_PlanetLabs.validKey, 'password': ''}
    self.access.run( url, credential )
    
  def saveImage(self, url, setFinished, setSave, setProgress):
    @QtCore.pyqtSlot(dict)
    def finished( response ):
      self.access.finished.disconnect( finished )
      if response['isOk']:
        self._clearResponse( response )
      setFinished( response ) # response[ 'totalReady' ]
      
    url = QtCore.QUrl.fromEncoded( url )
    self.access.finished.connect( finished )
    self.access.send_data.connect( setSave )
    self.access.status_download.connect( setProgress )
    credential = { 'user': API_PlanetLabs.validKey, 'password': ''}
    self.access.run( url, credential, False )

  @staticmethod
  def getUrlFilterScenesOrtho(filters):
    items = []
    for item in filters.iteritems():
      skey = str( item[0] )
      svalue = str( item[1] )
      items.append( ( skey, svalue ) )

    url = QtCore.QUrl( API_PlanetLabs.urlScenesOrtho) # urlScenesRapideye
    url.setQueryItems( items )

    return url.toEncoded()

  @staticmethod
  def getValue(jsonMetadataFeature, keys):
    dicMetadata = jsonMetadataFeature
    if not isinstance( jsonMetadataFeature, dict):
      dicMetadata = json.loads( jsonMetadataFeature )
    msgError = None
    e_keys = map( lambda item: "'%s'" % item, keys )
    try:
      value = reduce( lambda d, k: d[ k ], [ dicMetadata ] + keys )
    except KeyError as e:
      msgError = "Catalog Planet: Have invalid key: %s" % ' -> '.join( e_keys)
    except TypeError as e:
      msgError = "Catalog Planet: The last key is invalid: %s" % ' -> '.join( e_keys)

    if msgError is None and isinstance( value, dict):
      msgError = "Catalog Planet: Missing key: %s" % ' -> '.join( e_keys)

    return ( True, value ) if msgError is None else ( False, msgError ) 

  @staticmethod
  def getTextTreeMetadata( jsonMetadataFeature ):
    def fill_item(strLevel, value):
      if not isinstance( value, ( dict, list ) ):
        items[-1] += ": %s" % value
        return

      if isinstance( value, dict ):
        for key, val in sorted( value.iteritems() ):
          items.append( "%s%s" % ( strLevel, key ) )
          strLevel += signalLevel
          fill_item( strLevel, val )
          strLevel = strLevel[ : -1 * len( signalLevel ) ]
      return

      if isinstance( value, list ):
        for val in value:
          if not isinstance( value, ( dict, list ) ):
            items[-1] += ": %s" % value
          else:
            text = '[dict]' if isinstance( value, dict ) else '[list]'
            items.append( "%s%s" % ( strLevel, text ) )
            strLevel += signalLevel
            fill_item( strLevel, val )
            strLevel = strLevel[ : -1 * len( signalLevel ) ]

    signalLevel = "- "
    items = []
    fill_item( '', json.loads( jsonMetadataFeature ) )
    
    return '\n'.join( items )

  @staticmethod
  def getHtmlTreeMetadata(value, html):
    if isinstance( value, dict ):
      html += "<ul>"
      for key, val in sorted( value.iteritems() ):
        if not isinstance( val, dict ):
          html += "<li>%s: %s</li> " % ( key, val )
        else:
          html += "<li>%s</li> " % key
        html = API_PlanetLabs.getHtmlTreeMetadata( val, html )
      html += "</ul>"
      return html
    return html

  @staticmethod
  def getTextValuesMetadata( dicMetadataFeature ):
    def fill_item(value):
      def addValue(_value):
        _text = "'%s' = %s" % (", ".join( keys ),  _value )
        items.append( _text )

      if not isinstance( value, ( dict, list ) ):
        addValue( value )
        return

      if isinstance( value, dict ):
        for key, val in sorted( value.iteritems() ):
          keys.append( '"%s"' % key )
          fill_item( val )
          del keys[ -1 ]
      return

      if isinstance( value, list ):
        for val in value:
          if not isinstance( val, ( dict, list ) ):
            addValue( val )
          else:
            text = "[dict]" if isinstance( val, dict ) else "[list]"
            keys.append( '"%s"' % text )
            fill_item( val )
            del keys[ -1 ]

    keys = []
    items = []
    fill_item( dicMetadataFeature )
    
    return '\n'.join( items )

  @staticmethod
  def getQTreeWidgetMetadata( jsonMetadataFeature, parent=None ):
    def createTreeWidget():
      tw = QTreeWidget(parent)
      tw.setColumnCount( 2 )
      tw.header().hide()
      tw.clear()
      return tw
 
    def fill_item(item, value):
      item.setExpanded( True )
      if not isinstance( value, ( dict, list ) ):
        item.setData( 1, QtCore.Qt.DisplayRole, value )
        return

      if isinstance( value, dict ):
        for key, val in sorted( value.iteritems() ):
          child = QTreeWidgetItem()
          child.setText( 0, unicode(key) )
          item.addChild( child )
          fill_item( child, val )
      return

      if isinstance( value, list ):
        for val in value:
          if not isinstance( val, ( dict, list ) ):
            item.setData( 1, QtCore.Qt.DisplayRole, val )
          else:
            child = QTreeWidgetItem()
            item.addChild( child )
            text = '[dict]' if isinstance( value, dict ) else '[list]'
            child.setText( 0, text )
            fill_item( child , val )

          child.setExpanded(True)

    tw = createTreeWidget()
    fill_item( tw.invisibleRootItem(), json.loads( jsonMetadataFeature ) )
    tw.resizeColumnToContents( 0 )
    tw.resizeColumnToContents( 1 )
    
    return tw

  @staticmethod
  def getURL_TMS(feat, sbands):
    ( ok, item_type ) = API_PlanetLabs.getValue( feat['meta_json'], [ 'item_type' ] )
    url = API_PlanetLabs.urlTMS.format( item_type=item_type, item_id=feat['id'] )
    return url
