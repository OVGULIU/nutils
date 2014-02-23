from . import topology, util, function, element, log, numeric, debug, _
from scipy import spatial # for def mesh; import cannot be postponed apparently
import os, warnings

def _nansplit( data ):
  n = numeric.find( numeric.isnan( data.reshape( data.shape[0], -1 ) ).any( axis=1 ) )
  N = numeric.concatenate( [ [-1], n, [data.shape[0]] ] )
  return [ data[a:b] for a, b in zip( N[:-1]+1, N[1:] ) ]

class BasePlot( object ):
  'base class for plotting objects'

  def __init__ ( self, name, ndigits=0, index=None ):

    self.path = util.prop( 'dumpdir' )

    assert isinstance(ndigits,int) and ndigits >= 0, 'nonnegative integer required'
    if ndigits:
      if index is None:
        index = 1
        for filename in os.listdir( self.path ):
          if filename.startswith( name ):
            num = filename[len(name):].split('.')[0]
            if num.isdigit():
              index = max( index, int(num)+1 )
      name += str(index).rjust(ndigits,'0')

    self.name  = name
    self.names = None

  def __enter__( self ):
    'enter with block'

    return self

  def __exit__( self, *exc_info ):
    'exit with block'

    exc_type, exc_value, exc_tb = exc_info
    if exc_type == KeyboardInterrupt:
      pass
    elif exc_type:
      log.stack( repr(exc_value), debug.exception() )
    else:
      if self.names:
        for name in self.names:
          self.save( name )
        log.path( ', '.join( self.names ) )
      return True
    return False

  def save ( self, name ):
    return

class PyPlot( BasePlot ):
  'matplotlib figure'

  def __init__( self, name, imgtype=None, ndigits=3, index=None, **kwargs ):
    'constructor'

    BasePlot.__init__( self, name, ndigits=ndigits, index=index )

    import matplotlib
    matplotlib.use( 'Agg', warn=False )

    imgtype = util.prop( 'imagetype', 'png' ) if imgtype is None else imgtype
    self.names = [ self.name + '.' + ext for ext in imgtype.split(',') ]

    from matplotlib import pyplot
    self.__dict__.update( pyplot.__dict__ )
    self._fig = self.figure( **kwargs )

  def __exit__( self, *exc_info ):
    'exit with block'

    BasePlot.__exit__( self, *exc_info )
    try:
      self.close( self._fig )
    except:
      log.warning( 'failed to close figure' )

  def save( self, name ):
    'save images'

    self.savefig( os.path.join( self.path, name ) )
    #self.close()

  @staticmethod
  def _trimesh_class():
    'backport of TriMesh (function prevents unneccecary loading)'

    from matplotlib.collections import Collection
    from matplotlib.artist import allow_rasterization
    
    class TriMesh( Collection ):

      def __init__(self, xy, tri, **kwargs):
        Collection.__init__(self, **kwargs)
        self.xy = xy
        self.tri = tri
        self._facecolors = numeric.zeros([numeric.max(tri)+1,4]) # fully transparent
    
      @allow_rasterization
      def draw(self, renderer):
        if not self.get_visible():
          return
        renderer.open_group(self.__class__.__name__)
        transform = self.get_transform()
        verts = self.xy.T[self.tri]
        self.update_scalarmappable()
        colors = self._facecolors[self.tri]
        gc = renderer.new_gc()
        self._set_gc_clip(gc)
        gc.set_linewidth(self.get_linewidth()[0])
        renderer.draw_gouraud_triangles(gc, verts, colors, transform.frozen())
        gc.restore()
        renderer.close_group(self.__class__.__name__)

    return TriMesh

  def mesh( self, points, colors=None, edgecolors='k', edgewidth=None, triangulate='delaunay', setxylim=True, **kwargs ):
    'plot elemtwise mesh'

    assert numeric.isarray( points ) and points.dtype == float
    assert points.shape[-1] == 2
    if colors is not  None:
      assert numeric.isarray( colors ) and colors.dtype == float
      assert points.shape[:-1] == colors.shape

    if points.ndim == 3: # gridded data: nxpoints x nypoints x ndims

      assert colors is not None
      data = colors.ravel()
      xy = points.reshape( -1, 2 ).T
      ind = numeric.arange( xy.shape[1] ).reshape( points.shape[:-1] )
      vert1 = numeric.array([ ind[:-1,:-1].ravel(), ind[1:,:-1].ravel(), ind[:-1,1:].ravel() ]).T
      vert2 = numeric.array([ ind[1:,1:].ravel(), ind[1:,:-1].ravel(), ind[:-1,1:].ravel() ]).T
      triangles = numeric.concatenate( [vert1,vert2], axis=0 )
      edges = None

    elif points.ndim == 2: # mesh: npoints x ndims

      nans = numeric.isnan( points ).all( axis=1 )
      split = numeric.find( nans )
      if colors is not None:
        assert numeric.isnan( colors[split] ).all()
  
      P = []
      N = []
      C = []
      E = []
      npoints = 0
  
      for a, b in zip( numeric.concatenate([[0],split+1]), numeric.concatenate([split,[nans.size]]) ):
        np = b - a
        if np == 0:
          continue
        epoints = points[a:b]
        if colors is not None:
          ecolors = colors[a:b]
        if triangulate == 'delaunay':
          tri = spatial.Delaunay( epoints )
          vertices = tri.vertices
          e0 = [ edge[0] for edge in tri.convex_hull ]
          e1 = [ edge[1] for edge in tri.convex_hull ]
          last = e1.pop()
          hull = [ e0.pop(), last ]
          while e0:
            try:
              index = e0.index( last )
              last = e1[index]
            except ValueError:
              index = e1.index( last )
              last = e0[index]
            e0.pop( index )
            e1.pop( index )
            hull.append( last )
          assert hull[0] == hull[-1]
        elif triangulate == 'bezier':
          nquad = int( numeric.sqrt(np) + .5 )
          ntri = int( numeric.sqrt((2*np)+.25) )
          if nquad**2 == np:
            ind = numeric.arange(np).reshape(nquad,nquad)
            vert1 = numeric.array([ ind[:-1,:-1].ravel(), ind[1:,:-1].ravel(), ind[:-1,1:].ravel() ]).T
            vert2 = numeric.array([ ind[1:,1:].ravel(), ind[1:,:-1].ravel(), ind[:-1,1:].ravel() ]).T
            vertices = numeric.concatenate( [vert1,vert2], axis=0 )
            hull = numeric.concatenate([ ind[:,0], ind[-1,1:], ind[-2::-1,-1], ind[0,-2::-1] ])
          elif ntri * (ntri+1) == 2 * np:
            vert1 = [ ((2*ntri-i+1)*i)//2+numeric.array([j,j+1,j+ntri-i]) for i in range(ntri-1) for j in range(ntri-i-1) ]
            vert2 = [ ((2*ntri-i+1)*i)//2+numeric.array([j+1,j+ntri-i+1,j+ntri-i]) for i in range(ntri-1) for j in range(ntri-i-2) ]
            vertices = numeric.concatenate( [vert1,vert2], axis=0 )
            hull = numeric.concatenate([ numeric.arange(ntri), numeric.arange(ntri-1,0,-1).cumsum()+ntri-1, numeric.arange(ntri+1,2,-1).cumsum()[::-1]-ntri-1 ])
          else:
            raise Exception, 'cannot match points to a bezier scheme'
        else:
          raise Exception, 'unknown triangulation method %r' % triangulate
        P.append( epoints.T )
        N.append( vertices + npoints )
        if colors is not None:
          C.append( ecolors )
        E.append( epoints[hull] )
        npoints += np
  
      xy = numeric.concatenate( P, axis=1 )
      triangles = numeric.concatenate( N, axis=0 )
      if colors is not None:
        data = numeric.concatenate( C )
      edges = E

    else:

      raise Exception, 'invalid points shape %r' % ( points.shape, )
  
    TriMesh = self._trimesh_class()
    polycol = TriMesh( xy, triangles, rasterized=True, **kwargs )
    if colors is not None:
      polycol.set_array( data.view(numeric.ndarray) )

    if edges and edgecolors != 'none':
      from matplotlib.collections import LineCollection
      linecol = LineCollection( edges, linewidths=(edgewidth,) if edgewidth is not None else None )
      linecol.set_color( edgecolors )
      self.gca().add_collection( linecol )

    self.gca().add_collection( polycol )
    self.sci( polycol )
    
    if setxylim:
      xmin, ymin = numeric.min( xy, axis=1 )
      xmax, ymax = numeric.max( xy, axis=1 )
      self.xlim( xmin, xmax )
      self.ylim( ymin, ymax )

    if edgecolors != 'none':
      return polycol, linecol

    return polycol

  def polycol( self, verts, facecolors='none', **kwargs ):
    'add polycollection'
  
    from matplotlib import collections
    assert verts.ndim == 2 and verts.shape[1] == 2
    verts = _nansplit( verts )
    if facecolors != 'none':
      assert isinstance(facecolors,numeric.ndarray) and facecolors.shape == (len(verts),)
      array = facecolors
      facecolors = None
    polycol = collections.PolyCollection( verts, facecolors=facecolors, **kwargs )
    if facecolors is None:
      polycol.set_array( array )
    self.gca().add_collection( polycol )
    self.sci( polycol )
    return polycol

  def slope_triangle( self, x, y, fillcolor='0.9', edgecolor='k', xoffset=0, yoffset=0.1, slopefmt='{0:.1f}' ):
    '''Draw slope triangle for supplied y(x)
       - x, y: coordinates
       - xoffset, yoffset: distance graph & triangle (points)
       - fillcolor, edgecolor: triangle style
       - slopefmt: format string for slope number'''

    i, j = (-2,-1) if x[-1] < x[-2] else (-1,-2) # x[i] > x[j]
    if not all(numeric.isfinite(x[-2:])) or not all(numeric.isfinite(y[-2:])):
      log.warning( 'Not plotting slope triangle for +/-inf or nan values' )
      return

    from matplotlib import transforms
    shifttrans = self.gca().transData \
               + transforms.ScaledTranslation( xoffset, -yoffset, self.gcf().dpi_scale_trans )
    xscale, yscale = self.gca().get_xscale(), self.gca().get_yscale()

    # delta() checks if either axis is log or lin scaled
    delta = lambda a, b, scale: numeric.log10(float(a)/b) if scale=='log' else float(a-b) if scale=='linear' else None
    slope = delta( y[-2], y[-1], yscale ) / delta( x[-2], x[-1], xscale )
    if slope in (numeric.nan, numeric.inf, -numeric.inf):
      warnings.warn( 'Cannot draw slope triangle with slope: %s, drawing nothing' % str( slope ) )
      return slope

    # handle positive and negative slopes correctly
    xtup, ytup = ((x[i],x[j],x[i]), (y[j],y[j],y[i])) if slope > 0 else ((x[j],x[j],x[i]), (y[i],y[j],y[i]))
    a, b = (2/3., 1/3.) if slope > 0 else (1/3., 2/3.)
    xval = a*x[i]+b*x[j] if xscale=='linear' else x[i]**a * x[j]**b
    yval = b*y[i]+a*y[j] if yscale=='linear' else y[i]**b * y[j]**a

    self.fill( xtup, ytup,
      color=fillcolor,
      edgecolor=edgecolor,
      transform=shifttrans )

    self.text( xval, yval,
      slopefmt.format(slope),
      horizontalalignment='center',
      verticalalignment='center',
      transform=shifttrans )

    return slope

  def slope_trend( self, x, y, lt='k-', xoffset=.1, slopefmt='{0:.1f}' ):
    '''Draw slope triangle for supplied y(x)
       - x, y: coordinates
       - slopefmt: format string for slope number'''

    # TODO check for gca() loglog scale

    slope = numeric.log( y[-2]/y[-1] ) / numeric.log( x[-2]/x[-1] )
    C = y[-1] / x[-1]**slope

    self.loglog( x, C * x**slope, 'k-' )

    from matplotlib import transforms
    shifttrans = self.gca().transData \
               + transforms.ScaledTranslation( -xoffset if x[-1] < x[0] else xoffset, 0, self.gcf().dpi_scale_trans )

    self.text( x[-1], y[-1], slopefmt.format(slope),
      horizontalalignment='right' if x[-1] < x[0] else 'left',
      verticalalignment='center',
      transform=shifttrans )

    return slope

  def rectangle( self, x0, w, h, fc='none', ec='none', **kwargs ):
    'rectangle'

    from matplotlib import patches
    patch = patches.Rectangle( x0, w, h, fc=fc, ec=ec, **kwargs )
    self.gca().add_patch( patch )
    return patch

  def griddata( self, xlim, ylim, data ):
    'plot griddata'

    assert data.ndim == 2
    self.imshow( data.T, extent=(xlim[0],xlim[-1],ylim[0],ylim[-1]), origin='lower' )

  def cspy( self, A, **kwargs ): 
    'Like pyplot.spy, but coloring acc to 10^log of absolute values, where [0, inf, nan] show up in blue.'
    if not isinstance( A, numeric.ndarray ):
      A = A.toarray()
    if A.size < 2: # trivial case of 1x1 matrix
      A = A.reshape( 1, 1 )
    else:
      A = numeric.log10( numeric.abs( A ) )
      B = numeric.isinf( A ) | numeric.isnan( A ) # what needs replacement
      A[B] = ~B if numeric.all( B ) else numeric.amin( A[~B] ) - 1.
    self.pcolormesh( A, **kwargs )
    self.colorbar()
    self.ylim( self.ylim()[-1::-1] ) # invert y axis: equiv to MATLAB axis ij
    self.xlabel( r'$j$' )
    self.ylabel( r'$i$' )
    self.title( r'$^{10}\log a_{ij}$' )
    self.axis( 'tight' )

class DataFile( BasePlot ):
  """data file"""

  def __init__( self, name, index=None, ndigits=0, mode='w' ):
    'constructor'

    BasePlot.__init__( self, name, ndigits=ndigits, index=index )

    self.names = [name]
    self.fout  = open( os.path.join(self.path,name), mode )

  def save( self, name ):
    self.fout.close()

  def printline( self, line ):
    print >> self.fout, line 

  def printlist( self, lst, delim=' ', start='', stop='' ):
    print >> self.fout, start + delim.join(str(s) for s in lst)  + stop

class VTKFile( BasePlot ):
  'vtk file'

  def __init__( self, name, index=None, ndigits=0, ascii=False ):
    'constructor'

    BasePlot.__init__( self, name, ndigits=ndigits, index=index )

    self.names = self.name if self.name.lower().endswith('.vtu') else self.name + '.vtu',
    self.ascii = ascii

    import vtk 

    self.vtkmesh = vtk.vtkUnstructuredGrid()
    self.vtkmap = {
      (2,1): vtk.vtkLine(),
      (3,2): vtk.vtkTriangle(),
      (4,2): vtk.vtkQuad(),
      (4,3): vtk.vtkTetra(),
      (8,3): vtk.vtkVoxel(),
    }
    self.vtkXMLUnstructuredGridWriter = vtk.vtkXMLUnstructuredGridWriter
    self.vtkPoints = vtk.vtkPoints
    self.vtkVertex = vtk.vtkVertex
    self.vtkFloatArray = vtk.vtkFloatArray

  def save( self, name ):
    vtkWriter = self.vtkXMLUnstructuredGridWriter()
    vtkWriter.SetInput( self.vtkmesh )
    vtkWriter.SetFileName( os.path.join( self.path, name ) )
    if self.ascii:
      vtkWriter.SetDataModeToAscii()
    vtkWriter.Write()

  def vertices( self, points ):

    assert isinstance( points, numeric.ndarray ), 'Expected list of point arrays'

    vtkPoints = self.vtkPoints()
    vtkPoints.SetNumberOfPoints( sum(pts.shape[0] for pts in points) )

    cnt = 0
    for pts in points:
      if pts.shape[1] < 3:
        pts = numeric.concatenate([pts,numeric.zeros(shape=(pts.shape[0],3-pts.shape[1]))],axis=1)

      for point in pts:
        vtkPoints .SetPoint( cnt, point )
        cellpoints = self.vtkVertex().GetPointIds()
        cellpoints.SetId( 0, cnt )
        self.vtkmesh.InsertNextCell( self.vtkVertex().GetCellType(), cellpoints )
        cnt +=1

    self.vtkmesh.SetPoints( vtkPoints )

  def unstructuredgrid( self, points, npars=None ):
    """add unstructured grid"""

    if npars is not None:
      warnings.warn( 'npars is deprecated and can be safely removed', DeprecationWarning )

    pointcoords = []
    for pts in _nansplit( points ):
      npoints, ndims = pts.shape
      vtkelem = self.vtkmap[ pts.shape ]
      if ndims < 3:
        pts = numeric.concatenate([pts,numeric.zeros(shape=(npoints,3-ndims))],axis=1)

      cellpoints = vtkelem.GetPointIds()
      for i, coord in enumerate( pts ):
        cellpoints.SetId( i, len(pointcoords) )
        pointcoords.append( coord )
      self.vtkmesh.InsertNextCell( vtkelem.GetCellType(), cellpoints )

    vtkpoints = self.vtkPoints()
    vtkpoints.SetNumberOfPoints( len(pointcoords) )
    for i, coord in enumerate( pointcoords ):
      vtkpoints.SetPoint( i, coord )
    self.vtkmesh.SetPoints( vtkpoints )

  def celldataarray( self, name, data ):
    'add cell array'
    ncells = self.vtkmesh.GetNumberOfCells()
    assert ncells == data.shape[0], 'Cell data array should have %d entries' % ncells
    self.vtkmesh.GetCellData().AddArray( self.__vtkarray(name,data) )

  def pointdataarray( self, name, data ):
    'add cell array'
    npoints = self.vtkmesh.GetNumberOfPoints()
    isnan = numeric.isnan( data ).reshape( len(data), -1 ).any( axis=1 )
    contigdata = data[~isnan]
    assert npoints == contigdata.shape[0], 'Point data array should have %d entries' % npoints
    self.vtkmesh.GetPointData().AddArray( self.__vtkarray(name,contigdata) )

  def __vtkarray( self, name, data ):
    if data.ndim == 1:
      data = data[:,_]
    array = self.vtkFloatArray()
    array.SetName( name )
    array.SetNumberOfComponents( data.shape[1] )
    array.SetNumberOfTuples( data.shape[0] )
    for i,d in enumerate(data):
      array.SetTuple( i, d )
    return array

def writevtu( name, topo, coords, pointdata={}, celldata={}, ascii=False, superelements=False, maxrefine=3, ndigits=0, ischeme='gauss1', **kwargs ):
  'write vtu from coords function'

  with VTKFile( name, ascii=ascii, ndigits=ndigits ) as vtkfile:

    if not superelements:
      topo = topology.UnstructuredTopology( topo.get_simplices( maxrefine=maxrefine ), topo.ndims )
    else:
      topo = topology.UnstructuredTopology( filter(None,[elem if not isinstance(elem,element.TrimmedElement) else elem.elem for elem in topo]), topo.ndims )

    points = topo.elem_eval( coords, ischeme='vtk', separate=True )
    vtkfile.unstructuredgrid( points )

    if pointdata:  
      keys, values = zip( *pointdata.items() )
      arrays = topo.elem_eval( values, ischeme='vtk', separate=False )
      for key, array in zip( keys, arrays ):
        vtkfile.pointdataarray( key, array )

    if celldata:  
      keys, values = zip( *celldata.items() )
      arrays = topo.elem_mean( values, coords=coords, ischeme=ischeme )
      for key, array in zip( keys, arrays ):
        vtkfile.celldataarray( key, array )

######## OLD PLOTTING INTERFACE ############

class Pylab( object ):
  'matplotlib figure'

  def __init__( self, title, name='graph{0:03x}' ):
    'constructor'

    import matplotlib
    matplotlib.use( 'Agg', warn=False )

    if '.' not in name.format(0):
      imgtype = util.prop( 'imagetype', 'png' )
      name += '.' + imgtype

    if isinstance( title, (list,tuple) ):
      self.title = numeric.array( title, dtype=object )
      self.shape = self.title.shape
      if self.title.ndim == 1:
        self.title = self.title[:,_]
      assert self.title.ndim == 2
    else:
      self.title = numeric.array( [[ title ]] )
      self.shape = ()
    self.name = name

  def __enter__( self ):
    'enter with block'

    from matplotlib import pyplot
    pyplot.figure()
    n, m = self.title.shape
    axes = [ PylabAxis( pyplot.subplot(n,m,iax+1), title ) for iax, title in enumerate( self.title.ravel() ) ]
    return numeric.array( axes, dtype=object ).reshape( self.shape ) if self.shape else axes[0]

  def __exit__( self, exc, msg, tb ):
    'exit with block'

    if exc:
      log.error( 'ERROR: plot failed:', msg or exc )
      return #True

    from matplotlib import pyplot
    dumpdir = util.prop( 'dumpdir' )
    n = len( os.listdir( dumpdir ) )
    imgpath = util.getpath( self.name )
    pyplot.savefig( imgpath, format=imgpath.split('.')[-1] )
    os.chmod( imgpath, 0644 )
    pyplot.close()
    log.path( os.path.basename(imgpath) )

class PylabAxis( object ):
  'matplotlib axis augmented with nutils-specific functions'

  def __init__( self, ax, title ):
    'constructor'

    if title:
      ax.set_title( title )
    self._ax = ax

  def __getattr__( self, attr ):
    'forward getattr to axis'

    return getattr( self._ax, attr )

  @log.title
  def add_mesh( self, coords, topology, deform=0, color=None, edgecolors='none', linewidth=1, xmargin=0, ymargin=0, aspect='equal', cbar='vertical', title=None, ischeme='gauss2', cscheme='contour3', clim=None, frame=True, colormap=None ):
    'plot mesh'
  
    assert topology.ndims == 2
    from matplotlib import pyplot, collections
    poly = []
    values = []
    ndims, = coords.shape
    assert ndims in (2,3)
    if color:
      assert color.ndim == 0
      color = function.Tuple([ color, coords.iweights(ndims=2) ])
    plotcoords = coords + deform
    for elem in topology:
      C = plotcoords( elem, cscheme )
      if ndims == 3:
        C = project3d( C )
        cx, cy = numeric.hstack( [ C, C[:,:1] ] )
        if ( (cx[1:]-cx[:-1]) * (cy[1:]+cy[:-1]) ).sum() > 0:
          continue
      if color:
        c, w = color( elem, ischeme )
        values.append( numeric.mean( c, weights=w, axis=0 ) if c.ndim > 0 else c )
      poly.append( C )
  
    if values:
      elements = collections.PolyCollection( poly, edgecolors=edgecolors, linewidth=linewidth, rasterized=True )
      elements.set_array( numeric.asarray(values) )
      if colormap is not None:
        elements.set_cmap( pyplot.cm.gray if colormap is False else colormap )
      if cbar:
        pyplot.colorbar( elements, ax=self._ax, orientation=cbar )
    else:
      elements = collections.PolyCollection( poly, edgecolors='black', facecolors='none', linewidth=linewidth, rasterized=True )

    if clim:
      elements.set_clim( *clim )

    if ndims == 3:
      self.get_xaxis().set_visible( False )
      self.get_yaxis().set_visible( False )
      self.box( 'off' )

    self.add_collection( elements )
    vertices = numeric.concatenate( poly )
    xmin, ymin = vertices.min(0)
    xmax, ymax = vertices.max(0)

    if xmargin is not None:
      if not isinstance( xmargin, tuple ):
        xmargin = xmargin, xmargin
      self.set_xlim( xmin - xmargin[0], xmax + xmargin[1] )

    if ymargin is not None:
      if not isinstance( ymargin, tuple ):
        ymargin = ymargin, ymargin
      self.set_ylim( ymin - ymargin[0], ymax + ymargin[1] )

    if aspect:
      self.set_aspect( aspect )
      self.set_autoscale_on( False )

    if title:
      self.title( title )

    self.set_frame_on( frame )
    return elements
  
  def add_quiver( self, coords, topology, quiver, sample='uniform3', scale=None ):
    'quiver builder'
  
    xyuv = function.Concatenate( [ coords, quiver ] )
    XYUV = [ xyuv(elem,sample) for elem in log.iter( 'elem', topology ) ]
    self.quiver( *numeric.concatenate( XYUV, 0 ).T, scale=scale )

  def add_graph( self, xfun, yfun, topology, sample='contour10', logx=False, logy=False, **kwargs ):
    'plot graph of function on 1d topology'

    try:
      xfun = [ xf for xf in xfun ]
    except TypeError:
      xfun = [ xfun ]

    try:
      yfun = [ yf for yf in yfun ]
    except TypeError:
      yfun = [ yfun ]

    if len(xfun) == 1:
      xfun *= len(yfun)

    if len(yfun) == 1:
      yfun *= len(xfun)

    nfun = len(xfun)
    assert len(yfun) == nfun

    special_args = zip( *[ zip( [key]*nfun, val ) for (key,val) in kwargs.iteritems() if isinstance(val,list) and len(val) == nfun ] )
    XYD = [ ([],[],dict(d)) for d in special_args or [[]] * nfun ]
    xypairs = function.Tuple( [ function.Tuple(v) for v in zip( xfun, yfun, XYD ) ] )

    for elem in topology:
      for x, y, xyd in xypairs( elem, sample ):

        if y.ndim == 1 and y.shape[0] == 1:
          y = y[0]

        xyd[0].extend( x if x.ndim else [x] * y.size )
        xyd[0].append( numeric.nan )
        xyd[1].extend( y if y.ndim else [y] * x.size )
        xyd[1].append( numeric.nan )

    plotfun = self.loglog if logx and logy \
         else self.semilogx if logx \
         else self.semilogy if logy \
         else self.plot
    for x, y, d in XYD:
      kwargs.update(d)
      plotfun( x, y, **kwargs )

  def add_convplot( self, x, y, drop=0.8, shift=1.1, slope=True, **kwargs ): 
    """Convergence plot including slope triangle (below graph) for supplied y(x),
       drop  = distance graph & triangle,
       shift = distance triangle & text."""
    self.loglog( x, y, 'k.-', **kwargs )
    self.grid( True )
    if slope:
      if x[-1] < x[0]: # inverted order
        slx   = numeric.array( [x[-2], x[-2], x[-1], x[-2]] )
        sly   = numeric.array( [y[-2], y[-1], y[-1], y[-2]] )*drop
      if x[-1] > x[0]:
        slx   = numeric.array( [x[-1], x[-1], x[-2], x[-1]] )
        sly   = numeric.array( [y[-1], y[-2], y[-2], y[-1]] )/drop
      # slope = r'$%2.1f$' % (y[-2]*x[-1]/(x[-2]*y[-1]))
      slope = r'$%2.1f$' % (numeric.diff( numeric.log10( y[-2:] ) )/numeric.diff( numeric.log10( x[-2:] ) ))
      self.loglog( slx, sly, color='k', label='_nolegend_' )
      self.text( slx[-1]*shift, numeric.mean( sly[:2] )*drop, slope )

def project3d( C ):
  sqrt2 = numeric.sqrt( 2 )
  sqrt3 = numeric.sqrt( 3 )
  sqrt6 = numeric.sqrt( 6 )
  R = numeric.array( [[ sqrt3, 0, -sqrt3 ], [ 1, 2, 1 ], [ sqrt2, -sqrt2, sqrt2 ]] ) / sqrt6
  return numeric.transform( C, R[:,::2], axis=0 )

def preview( coords, topology, cscheme='contour8' ):
  'preview function'

  if topology.ndims == 3:
    topology = topology.boundary

  from matplotlib import pyplot, collections
  if coords.shape[0] == 2:
    mesh( coords, topology, cscheme=cscheme )
  elif coords.shape[0] == 3:
    polys = [ [] for i in range(4) ]
    for elem in topology:
      contour = coords( elem, cscheme )
      polys[0].append( project3d( contour ).T )
      polys[1].append( contour[:2].T )
      polys[2].append( contour[1:].T )
      polys[3].append( contour[::2].T )
    for iplt, poly in enumerate( polys ):
      elements = collections.PolyCollection( poly, edgecolors='black', facecolors='none', linewidth=1, rasterized=True )
      ax = pyplot.subplot( 2, 2, iplt+1 )
      ax.add_collection( elements )
      xmin, ymin = numeric.min( [ numeric.min(p,axis=0) for p in poly ], axis=0 )
      xmax, ymax = numeric.max( [ numeric.max(p,axis=0) for p in poly ], axis=0 )
      d = .02 * (xmax-xmin+ymax-ymin)
      pyplot.axis([ xmin-d, xmax+d, ymin-d, ymax+d ])
      if iplt == 0:
        ax.get_xaxis().set_visible( False )
        ax.get_yaxis().set_visible( False )
        pyplot.box( 'off' )
      else:
        pyplot.title( '?ZXY'[iplt] )
  else:
    raise Exception, 'need 2D or 3D coordinates'
  pyplot.show()

# vim:shiftwidth=2:foldmethod=indent:foldnestmax=2
