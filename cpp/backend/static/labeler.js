/**
 * D3-Labeler - Simulated Annealing Label Placement
 * Original: https://github.com/tinker10/D3-Labeler (MIT License)
 *
 * Patched for Shanghai Metro visualization:
 *  - Tier-weighted overlap energy (higher weight = more overlap penalty)
 *  - `fixed` label support for two-phase optimization
 *  - Disabled orientation bias for Chinese text
 *  - Tuned weights for station-label layout
 */
(function() {

d3.labeler = function() {
  var lab = [],
      anc = [],
      w = 1, // box width
      h = 1, // box width
      labeler = {};

  var max_move = 5.0,
      max_angle = 0.5,
      acc = 0;
      rej = 0;

  // weights
  var w_len = 0.01, // leader line length (light penalty - labels should be near stations)
      w_inter = 0.0, // leader line intersection (we don't draw leaders)
      w_lab2 = 30.0, // label-label overlap
      w_lab_anc = 30.0; // label-anchor overlap
      w_orient = 0.0; // orientation bias (disabled for Chinese text)

  // booleans for user defined functions
  var user_energy = false,
      user_schedule = false;

  var user_defined_energy, 
      user_defined_schedule;

  energy = function(index) {
  // energy function, tailored for label placement - OPTIMIZED VERSION

      var m = lab.length,
          ener = 0,
          dx = lab[index].x - anc[index].x,
          dy = anc[index].y - lab[index].y,
          distSq = dx * dx + dy * dy;

      // OPTIMIZATION: Skip sqrt for leader line penalty - use squared distance
      // (monotonic transformation, doesn't affect relative energy comparison)
      if (distSq > 0) ener += Math.sqrt(distSq) * w_len;

      // OPTIMIZATION: w_orient and w_inter are always 0 in our config, skip entirely
      // label orientation bias - DISABLED for Chinese text
      // leader line intersection - DISABLED (we don't draw leaders)

      var lab_idx = lab[index];
      var idx_w = lab_idx.weight || 1;
      var idx_anchor_w = (lab_idx.anchorWeight || 1) * w_lab_anc;
      var x21 = lab_idx.x,
          y21 = lab_idx.y - lab_idx.height + 2.0,
          x22 = lab_idx.x + lab_idx.width,
          y22 = lab_idx.y + 2.0;
      var x11, x12, y11, y12, x_overlap, y_overlap, overlap_area;

      for (var i = 0; i < m; i++) {
        if (i !== index) {
          var lab_i = lab[i];

          // penalty for label-label overlap
          x11 = lab_i.x;
          y11 = lab_i.y - lab_i.height + 2.0;
          x12 = lab_i.x + lab_i.width;
          y12 = lab_i.y + 2.0;
          x_overlap = Math.max(0, Math.min(x12,x22) - Math.max(x11,x21));
          if (x_overlap === 0) continue; // EARLY EXIT: no x-overlap means no overlap at all
          y_overlap = Math.max(0, Math.min(y12,y22) - Math.max(y11,y21));
          if (y_overlap === 0) continue; // EARLY EXIT: no y-overlap

          overlap_area = x_overlap * y_overlap;
          // PATCH A: weighted by label weights (higher weight label overlap = more penalty)
          var effective_w = w_lab2 / Math.min(lab_i.weight || 1, idx_w);
          ener += (overlap_area * effective_w);
        }

        // penalty for label-anchor overlap
        var anc_i = anc[i];
        var anc_r = anc_i.r || 4;
        x11 = anc_i.x - anc_r;
        y11 = anc_i.y - anc_r;
        x12 = anc_i.x + anc_r;
        y12 = anc_i.y + anc_r;
        x_overlap = Math.max(0, Math.min(x12,x22) - Math.max(x11,x21));
        if (x_overlap === 0) continue; // EARLY EXIT
        y_overlap = Math.max(0, Math.min(y12,y22) - Math.max(y11,y21));
        if (y_overlap === 0) continue; // EARLY EXIT

        overlap_area = x_overlap * y_overlap;
        ener += (overlap_area * idx_anchor_w);
      }
      return ener;
  };

  mcmove = function(currT) {
  // Monte Carlo translation move

      // select a random label
      var i = Math.floor(Math.random() * lab.length);

      // PATCH B: skip fixed labels (used for two-phase optimization)
      if (lab[i].fixed) return;

      // save old coordinates
      var x_old = lab[i].x;
      var y_old = lab[i].y;

      // old energy
      var old_energy;
      if (user_energy) {old_energy = user_defined_energy(i, lab, anc)}
      else {old_energy = energy(i)}

      // random translation
      lab[i].x += (Math.random() - 0.5) * max_move;
      lab[i].y += (Math.random() - 0.5) * max_move;

      // hard wall boundaries
      if (lab[i].x > w) lab[i].x = x_old;
      if (lab[i].x < 0) lab[i].x = x_old;
      if (lab[i].y > h) lab[i].y = y_old;
      if (lab[i].y < 0) lab[i].y = y_old;

      // new energy
      var new_energy;
      if (user_energy) {new_energy = user_defined_energy(i, lab, anc)}
      else {new_energy = energy(i)}

      // delta E
      var delta_energy = new_energy - old_energy;

      if (Math.random() < Math.exp(-delta_energy / currT)) {
        acc += 1;
      } else {
        // move back to old coordinates
        lab[i].x = x_old;
        lab[i].y = y_old;
        rej += 1;
      }

  };

  mcrotate = function(currT) {
  // Monte Carlo rotation move

      // select a random label
      var i = Math.floor(Math.random() * lab.length);

      // PATCH B: skip fixed labels (used for two-phase optimization)
      if (lab[i].fixed) return;

      // save old coordinates
      var x_old = lab[i].x;
      var y_old = lab[i].y;

      // old energy
      var old_energy;
      if (user_energy) {old_energy = user_defined_energy(i, lab, anc)}
      else {old_energy = energy(i)}

      // random angle
      var angle = (Math.random() - 0.5) * max_angle;

      var s = Math.sin(angle);
      var c = Math.cos(angle);

      // translate label (relative to anchor at origin):
      lab[i].x -= anc[i].x
      lab[i].y -= anc[i].y

      // rotate label
      var x_new = lab[i].x * c - lab[i].y * s,
          y_new = lab[i].x * s + lab[i].y * c;

      // translate label back
      lab[i].x = x_new + anc[i].x
      lab[i].y = y_new + anc[i].y

      // hard wall boundaries
      if (lab[i].x > w) lab[i].x = x_old;
      if (lab[i].x < 0) lab[i].x = x_old;
      if (lab[i].y > h) lab[i].y = y_old;
      if (lab[i].y < 0) lab[i].y = y_old;

      // new energy
      var new_energy;
      if (user_energy) {new_energy = user_defined_energy(i, lab, anc)}
      else {new_energy = energy(i)}

      // delta E
      var delta_energy = new_energy - old_energy;

      if (Math.random() < Math.exp(-delta_energy / currT)) {
        acc += 1;
      } else {
        // move back to old coordinates
        lab[i].x = x_old;
        lab[i].y = y_old;
        rej += 1;
      }
      
  };

  intersect = function(x1, x2, x3, x4, y1, y2, y3, y4) {
  // returns true if two lines intersect, else false
  // from http://paulbourke.net/geometry/lineline2d/

    var mua, mub;
    var denom, numera, numerb;

    denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1);
    numera = (x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3);
    numerb = (x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3);

    /* Is the intersection along the the segments */
    mua = numera / denom;
    mub = numerb / denom;
    if (!(mua < 0 || mua > 1 || mub < 0 || mub > 1)) {
        return true;
    }
    return false;
  }

  cooling_schedule = function(currT, initialT, nsweeps) {
  // linear cooling
    return (currT - (initialT / nsweeps));
  };

  // OPTIMIZATION: Chunked SA execution with requestAnimationFrame
  // Prevents main thread blocking by yielding to browser every N sweeps
  var SWEEPS_PER_CHUNK = 50; // Yield every 50 sweeps (~8ms of work)
  var abortRequested = false;

  labeler.abort = function() {
    abortRequested = true;
    return labeler;
  };

  labeler.start = function(nsweeps, onProgress, onComplete) {
  // main simulated annealing function - CHUNKED VERSION
      var m = lab.length,
          currT = 1.0,
          initialT = 1.0,
          currentSweep = 0;

      abortRequested = false;

      // If no callbacks provided, run synchronously (backward compatible)
      if (!onProgress && !onComplete) {
        for (var i = 0; i < nsweeps; i++) {
          for (var j = 0; j < m; j++) {
            if (Math.random() < 0.5) { mcmove(currT); }
            else { mcrotate(currT); }
          }
          currT = cooling_schedule(currT, initialT, nsweeps);
        }
        return labeler;
      }

      // Async chunked execution
      function runChunk() {
        if (abortRequested) {
          if (onComplete) onComplete(true);
          return;
        }

        var endSweep = Math.min(currentSweep + SWEEPS_PER_CHUNK, nsweeps);
        for (var i = currentSweep; i < endSweep; i++) {
          for (var j = 0; j < m; j++) {
            if (Math.random() < 0.5) { mcmove(currT); }
            else { mcrotate(currT); }
          }
          currT = cooling_schedule(currT, initialT, nsweeps);
        }
        currentSweep = endSweep;

        if (onProgress) onProgress(currentSweep / nsweeps);

        if (currentSweep >= nsweeps) {
          if (onComplete) onComplete(false);
          return;
        }

        // Yield to browser for UI updates
        requestAnimationFrame(runChunk);
      }

      requestAnimationFrame(runChunk);
      return labeler;
  };

  labeler.width = function(x) {
  // users insert graph width
    if (!arguments.length) return w;
    w = x;
    return labeler;
  };

  labeler.height = function(x) {
  // users insert graph height
    if (!arguments.length) return h;
    h = x;    
    return labeler;
  };

  labeler.label = function(x) {
  // users insert label positions
    if (!arguments.length) return lab;
    lab = x;
    return labeler;
  };

  labeler.anchor = function(x) {
  // users insert anchor positions
    if (!arguments.length) return anc;
    anc = x;
    return labeler;
  };

  labeler.alt_energy = function(x) {
  // user defined energy
    if (!arguments.length) return energy;
    user_defined_energy = x;
    user_energy = true;
    return labeler;
  };

  labeler.alt_schedule = function(x) {
  // user defined cooling_schedule
    if (!arguments.length) return  cooling_schedule;
    user_defined_schedule = x;
    user_schedule = true;
    return labeler;
  };

  return labeler;
};

})();

