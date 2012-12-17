from . import core
import sys, time, os

error    = lambda msg, end='\n': log( 0, msg, end )
warning  = lambda msg, end='\n': log( 1, msg, end )
info     = lambda msg, end='\n': log( 2, msg, end )
progress = lambda msg, end='\n': log( 3, msg, end )
debug    = lambda msg, end='\n': log( 4, msg, end )

def log( level, msg, end ):
  'log text'

  verbosity = core.getprop( 'verbose', 0 )
  if verbosity < level:
    return

  sys.stdout.write( msg + end )
  sys.stdout.flush()

  html = core.getprop( 'html', False )
  if html:
    html.write( msg + end )

class ProgressBar( object ):
  'progress bar class'

  def __init__( self ):
    'constructor'

    self.x = 0
    self.t0 = time.time()
    self.length = core.getprop( 'linewidth', 50 )
    self.endtext = ''

  def add( self, text ):
    'add text'

    self.length -= len(text) + 1
    progress( text + ' ', end='' )

  def add_to_end( self, text ):
    'add to after progress bar'

    self.length -= len(text) + 1
    self.endtext += ' ' + text

  def bar( self, iterable, n=None ):
    'iterate'

    if n is None:
      n = len( iterable )
    for i, item in enumerate( iterable ):
      self.update( i, n )
      yield item

  def update( self, i, n ):
    'update'

    x = int( (i+1) * self.length ) // (n+1)
    if self.x < x <= self.length:
      progress( '-' * (x-self.x), end='' )
      self.x = x

  def __del__( self ):
    'destructor'

    dt = '%.2f' % ( time.time() - self.t0 )
    dts = dt[1:] if dt[0] == '0' else \
          dt[:3] if len(dt) <= 6 else \
          '%se%d' % ( dt[0], len(dt)-3 )
    progress( '-' * (self.length-self.x) + self.endtext + ' ' + dts )

def progressbar( iterable, title='iterating' ):
  'show progressbar while iterating'

  progress = ProgressBar()
  progress.add( title )
  return progress.bar( iterable )

class HtmlWriter( object ):
  'html writer'

  html = None

  def __init__( self, htmlfile ):
    'constructor'

    self.basedir = os.path.dirname( htmlfile )
    self.html = open( htmlfile, 'w' )
    self.html.write( HTMLHEAD )
    if 'public_html/' in htmlfile:
      import pwd
      username = pwd.getpwuid( os.getuid() ).pw_name
      permanent = 'http://~%s/%s' % ( username, htmlfile.split('public_html/',1)[1] )
    else:
      permanent = 'file://%s' % htmlfile
    self.html.write( '<a href="%s">[permalink]</a>\n\n' % permanent )
    self.html.flush()

    import re
    self.pattern = re.compile( r'\b(\w+[.]\w+)\b' )

  def filerep( self, match ):
    'replace file occurrences'

    name = match.group(0)
    path = os.path.join( self.basedir, name )
    if not os.path.isfile( path ):
      return name
    return r'<a href="%s">%s</a>' % (name,name)

  def write( self, s ):
    'write string'

    self.html.write( self.pattern.sub( self.filerep, s ) )
    self.html.flush()

  def __del__( self ):
    'destructor'

    if self.html is not None:
      self.html.write( HTMLFOOT )

HTMLHEAD = '''\
<html>
<head>
<script type='application/javascript'>

var i_focus = 0; // currently focused anchor element
var anchors; // list of all anchors (ordered by height)
var focus; // = anchors[i_focus] after first mouse move
var preview; // preview div element
var Y = 0; // current mouse height relative to window

findclosest = function () {
  y = Y + document.body.scrollTop - anchors[0].offsetHeight / 2;
  var dy = y - anchors[i_focus].offsetTop;
  if ( dy > 0 ) {
    for ( var i = i_focus; i < anchors.length-1; i++ ) {
      var yd = anchors[i+1].offsetTop - y;
      if ( yd > 0 ) return i + ( yd < dy );
      dy = -yd;
    }
    return anchors.length - 1;
  }
  else {
    for ( var i = i_focus; i > 0; i-- ) {
      var yd = anchors[i-1].offsetTop - y;
      if ( yd < 0 ) return i - ( yd > dy );
      dy = -yd;
    }
    return 0;
  }
}

refocus = function () {
  // update preview image if necessary
  var newfocus = anchors[ findclosest() ];
  if ( focus ) {
    if ( focus == newfocus ) return;
    focus.classList.remove( 'highlight' );
    focus.classList.remove( 'loading' );
  }
  focus = newfocus;
  focus.classList.add( 'loading' );
  newobj = document.createElement( 'img' );
  newobj.setAttribute( 'width', '600px' );
  newobj.onclick = function () { document.location.href=focus.getAttribute('href'); };
  newobj.onload = function () {
    preview.innerHTML='';
    preview.appendChild(this);
    focus.classList.add( 'highlight' )
    focus.classList.remove( 'loading' );
  };
  newobj.setAttribute( 'src', focus.getAttribute('href') );
}

window.onload = function() {
  // set up anchor list, preview pane, document events
  nodelist = document.getElementsByTagName('a');
  anchors = []
  for ( i = 0; i < nodelist.length; i++ ) {
    var url = nodelist[i].getAttribute('href');
    var ext = url.split('.').pop();
    var idx = ['png','svg','jpg','jpeg'].indexOf(ext);
    if ( idx != -1 ) anchors.push( nodelist[i] );
  }
  if ( anchors.length == 0 ) return;
  preview = document.createElement( 'div' );
  preview.setAttribute( 'id', 'preview' );
  document.body.appendChild( preview );
  document.onmousemove = function (event) { Y=event.clientY; refocus(); };
  document.onscroll = refocus;
};

</script>
<style>

a { text-decoration: none; color: blue; }
a.loading { color: green; }
a.highlight { color: red; }

#preview {
  position: fixed;
  top: 10px;
  right: 10px;
  border: 1px solid gray;
  padding: 0px;
}

</style>
</head>
<body>
<pre>'''

HTMLFOOT = '''\
</pre>
</body>
</html>
'''

# vim:shiftwidth=2:foldmethod=indent:foldnestmax=2
