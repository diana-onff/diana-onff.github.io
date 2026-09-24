/* ================================================================== *
 * Geometry on the sphere, and where a position sits in radio terms.
 *
 * Pure functions only: no DOM, no globals of the app, nothing that needs
 * the page to have loaded. That is what lets this file load second, right
 * after core.js, and be tested on its own. The point-in-polygon test,
 * haversine and bearing used to live in geo.js and spots.js; they moved
 * here so there is one copy of each, used by the map as well as by the
 * Info tab (nearinfo.js).
 * ================================================================== */

/* ---------- basics ---------- */
const EARTH_R = 6371000;

function pointInRing(x,y,ring){
  let inside=false;
  for(let i=0,j=ring.length-1;i<ring.length;j=i++){
    const [xi,yi]=ring[i], [xj,yj]=ring[j];
    if(((yi>y)!==(yj>y)) && (x < (xj-xi)*(y-yi)/(yj-yi)+xi)) inside=!inside;
  }
  return inside;
}
/* geom: anything with MultiPolygon-shaped coordinates. */
function pointInGeom(x,y,geom){
  for(const poly of geom.coordinates){
    if(pointInRing(x,y,poly[0])){
      let inHole=false;
      for(let h=1;h<poly.length;h++) if(pointInRing(x,y,poly[h])) inHole=true;
      if(!inHole) return true;
    }
  }
  return false;
}
function haversine(lat1,lon1,lat2,lon2){
  const t=Math.PI/180;
  const a=Math.sin((lat2-lat1)*t/2)**2 +
          Math.cos(lat1*t)*Math.cos(lat2*t)*Math.sin((lon2-lon1)*t/2)**2;
  return 2*EARTH_R*Math.asin(Math.sqrt(Math.min(1, a)));
}
/* Initial great-circle bearing, 0-360, north = 0. */
function bearing(lat1,lon1,lat2,lon2){
  const t=Math.PI/180, y=Math.sin((lon2-lon1)*t)*Math.cos(lat2*t);
  const x=Math.cos(lat1*t)*Math.sin(lat2*t)-Math.sin(lat1*t)*Math.cos(lat2*t)*Math.cos((lon2-lon1)*t);
  return (Math.atan2(y,x)/t+360)%360;
}
/* Where you end up after `dist` metres on bearing `brg` degrees. */
function destination(lat, lon, brg, dist){
  const t = Math.PI/180, d = dist / EARTH_R, b = brg * t, p1 = lat * t, l1 = lon * t;
  const p2 = Math.asin(Math.sin(p1)*Math.cos(d) + Math.cos(p1)*Math.sin(d)*Math.cos(b));
  const l2 = l1 + Math.atan2(Math.sin(b)*Math.sin(d)*Math.cos(p1), Math.cos(d) - Math.sin(p1)*Math.sin(p2));
  return [p2 / t, ((l2 / t + 540) % 360) - 180];
}

/* ---------- Maidenhead locator ----------
   pairs = 3 gives the usual six characters (JO21EE), 4 gives eight
   (JO21EE45). Upper case throughout, as Diana has always written it. The
   north pole and the date line are clamped just inside, otherwise lat 90
   would ask for a field that does not exist. */
function maidenhead(lat, lon, pairs){
  pairs = pairs || 3;
  let x = Math.min(Math.max(lon + 180, 0), 360 - 1e-9);
  let y = Math.min(Math.max(lat + 90, 0), 180 - 1e-9);
  const A = 65;
  let out = String.fromCharCode(A + Math.floor(x / 20), A + Math.floor(y / 10));
  x %= 20; y %= 10;
  let w = 2, h = 1;                       // the square: 2 by 1 degrees
  out += Math.floor(x / w) + '' + Math.floor(y / h);
  x %= w; y %= h;
  for(let p = 3; p <= pairs; p++){
    if(p % 2){                            // letters: 24 steps
      w /= 24; h /= 24;
      out += String.fromCharCode(A + Math.floor(x / w), A + Math.floor(y / h));
    } else {                              // digits: 10 steps
      w /= 10; h /= 10;
      out += Math.floor(x / w) + '' + Math.floor(y / h);
    }
    x %= w; y %= h;
  }
  return out;
}

/* ---------- CQ zone, ITU zone, ITU region ----------
   `list` is one of the arrays in geo/radio-zones.json: [{n, b:[bbox], c:[...]}].
   Longitudes there are not folded into -180..180 (a zone across the date line
   is drawn in one piece, see build/radiozones.py), so each position is tried
   as lon, lon+360 and lon-360. Returns every zone number that holds the
   point, smallest first: normally one, two where the source polygons
   overlap, none near the poles where the source has nothing. */
function zonesAt(list, lat, lon){
  const hits = [];
  for(const x of [lon, lon + 360, lon - 360]){
    for(const z of list){
      const b = z.b;
      if(x < b[0] || x > b[2] || lat < b[1] || lat > b[3]) continue;
      if(pointInGeom(x, lat, {coordinates: z.c}) && !hits.includes(z.n)) hits.push(z.n);
    }
  }
  return hits.sort((a, b) => a - b);
}

/* The zone lines are the source's lines simplified to about 3 km, and a GPS
   position has its own margin. So besides the zone at the point itself, this
   looks at eight points on a circle around it: if any of them lands in a
   different zone, the answer is "this one, but the boundary is close enough
   that it could be that one". Better an honest "14 or 40" than a confident
   wrong one on a ship in the Norwegian Sea. */
const ZONE_EDGE_M = 3500;
function zoneAround(list, lat, lon, accuracy){
  const here = zonesAt(list, lat, lon);
  const r = Math.max(ZONE_EDGE_M, accuracy || 0);
  const also = [];
  for(let k = 0; k < 8; k++){
    const [pl, po] = destination(lat, lon, k * 45, r);
    for(const n of zonesAt(list, pl, po)) if(!here.includes(n) && !also.includes(n)) also.push(n);
  }
  return {here, also: also.sort((a, b) => a - b)};
}

/* ---------- nearest points: a 1 by 1 degree grid ----------
   65,000 WWFF references worldwide. Measuring all of them on every position
   update works, but costs the battery for nothing: all but a few hundred are
   thousands of kilometres away. So they are sorted once into one-degree
   cells, and a search starts in your own cell and widens ring by ring, only
   as far as it has to. */
function gridIndex(points){        // points: [{lat, lon, ...}]
  const cells = new Map();
  for(const p of points){
    if(!isFinite(p.lat) || !isFinite(p.lon)) continue;
    const key = gridKey(Math.floor(p.lat), Math.floor(p.lon));
    let c = cells.get(key);
    if(!c) cells.set(key, c = []);
    c.push(p);
  }
  return {cells, size: points.length};
}
function gridKey(row, col){
  col = ((col % 360) + 360) % 360;   // 0..359, so the date line has no seam
  return row * 1000 + col;
}
/* The k nearest, nearest first, each with its distance `d` in metres. */
function nearestIn(grid, lat, lon, k){
  const row0 = Math.floor(lat), col0 = Math.floor(lon);
  const best = [];                   // kept sorted, at most k long
  const consider = p => {
    const d = haversine(lat, lon, p.lat, p.lon);
    if(best.length === k && d >= best[k - 1].d) return;
    best.push(Object.assign({}, p, {d}));
    best.sort((a, b) => a.d - b.d);
    if(best.length > k) best.pop();
  };
  const seen = new Set();
  const visit = (r, c) => {
    if(r < -90 || r > 89) return;
    const key = gridKey(r, c);
    if(seen.has(key)) return;
    seen.add(key);
    const cell = grid.cells.get(key);
    if(cell) cell.forEach(consider);
  };
  const t = Math.PI / 180;
  for(let ring = 0; ring <= 180; ring++){
    // Only the edge of the square, each cell once.
    for(let dc = -ring; dc <= ring; dc++){ visit(row0 - ring, col0 + dc); visit(row0 + ring, col0 + dc); }
    for(let dr = -ring + 1; dr <= ring - 1; dr++){ visit(row0 + dr, col0 - ring); visit(row0 + dr, col0 + ring); }
    if(best.length < k || ring >= 90) continue;
    // Everything in the next ring lies at least `ring` whole cells away: that
    // many degrees of latitude (R times the angle), or that many degrees of
    // longitude, whose nearest point is the cross-track distance to that
    // meridian: asin(cos(lat) * sin(dlon)). Stop once even the smaller of
    // the two is further than the furthest of the k we already have.
    const gap = Math.min(ring * t * EARTH_R,
                         EARTH_R * Math.asin(Math.min(1, Math.cos(lat * t) * Math.sin(ring * t))));
    if(gap >= best[k - 1].d) break;
  }
  return best;
}

/* ---------- small formatting helpers ---------- */
/* 51.17500 N, 4.34500 E, the way a logbook writes it. */
function fmtLatLon(lat, lon){
  return `${Math.abs(lat).toFixed(5)}° ${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lon).toFixed(5)}° ${lon >= 0 ? 'E' : 'W'}`;
}
/* 51°10'30.0" N 4°20'42.0" E */
function fmtDMS(lat, lon){
  const one = (v, pos, neg) => {
    const a = Math.abs(v);
    let d = Math.floor(a), m = Math.floor((a - d) * 60), s = ((a - d) * 60 - m) * 60;
    if(s >= 59.95){ s = 0; m += 1; }
    if(m >= 60){ m = 0; d += 1; }
    return `${d}°${String(m).padStart(2, '0')}'${s.toFixed(1).padStart(4, '0')}" ${v >= 0 ? pos : neg}`;
  };
  return `${one(lat, 'N', 'S')} ${one(lon, 'E', 'W')}`;
}
