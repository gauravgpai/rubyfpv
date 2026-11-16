#!/usr/bin/haserl
<%in p/common.cgi %>
<%
[ -f /etc/lens.conf ] && . /etc/lens.conf
%>
<%in p/header.cgi %>

<div class="row g-4">
	<div class="col-12 col-lg-6">
		<div class="card"><div class="card-body">
			<% card_head "Zoom and focus" %>
			<p class="small text-secondary">
				Drag a slider away from the middle to move the lens, or hold a
				button; it stops when you let go. The arrow keys work too: up
				and down zoom, left and right focus.
			</p>

			<label for="lens-zoom" class="form-label mb-0">Zoom</label>
			<div class="d-flex align-items-center gap-2 mb-3">
				<span class="small text-secondary">out</span>
				<input type="range" class="form-range lens-jog" id="lens-zoom" min="-1" max="1" step="1" value="0"
					data-neg="zoom-out" data-pos="zoom-in">
				<span class="small text-secondary">in</span>
			</div>
			<label for="lens-focus" class="form-label mb-0">Focus</label>
			<div class="d-flex align-items-center gap-2 mb-3">
				<span class="small text-secondary">near</span>
				<input type="range" class="form-range lens-jog" id="lens-focus" min="-1" max="1" step="1" value="0"
					data-neg="focus-near" data-pos="focus-far">
				<span class="small text-secondary">far</span>
			</div>
			<p class="small text-secondary">
				The sliders spring back to the middle: the lens board reports
				no position, so they set a direction, not a place.
				<% if [ "${LENS_AF:-1}" = 1 ]; then %>Autofocus is on: the lens
				refocuses by itself, also after a zoom, and will pull a manual
				focus move back. Set <code>LENS_AF=0</code> in
				<code>/etc/lens.conf</code> for manual focus.<% fi %>
			</p>

			<div class="d-flex flex-wrap gap-2 mb-3">
				<button type="button" class="btn btn-primary lens-btn" data-cmd="zoom-in">Zoom in</button>
				<button type="button" class="btn btn-primary lens-btn" data-cmd="zoom-out">Zoom out</button>
			</div>
			<div class="d-flex flex-wrap gap-2 mb-3">
				<button type="button" class="btn btn-secondary lens-btn" data-cmd="focus-near">Focus near</button>
				<button type="button" class="btn btn-secondary lens-btn" data-cmd="focus-far">Focus far</button>
			</div>
			<button type="button" class="btn btn-outline-danger" id="lens-stop">Stop</button>

			<p class="small mt-3 mb-0" id="lens-status" role="status" aria-live="polite">Ready.</p>
		</div></div>
	</div>
	<div class="col-12 col-lg-6">
		<div class="card"><div class="card-body">
			<% card_head "Lens port" %>
			<p class="small text-secondary mb-2">
				Pelco-D on <code><%= ${LENS_PORT:-/dev/ttyAMA0} %></code> at
				<%= ${LENS_BAUD:-57600} %> baud, address <%= ${LENS_ADDR:-1} %>.
				Change these in <code>/etc/lens.conf</code>.
			</p>
			<p class="small text-secondary mb-0">
				The live picture is on the <a href="live.cgi">Live</a> page;
				open it in a second window to see the lens move.
			</p>
		</div></div>
	</div>
</div>

<script>
(function () {
	var status = document.getElementById('lens-status');
	var moving = null;

	function send(cmd) {
		return fetch('/cgi-bin/j/lens.cgi?cmd=' + encodeURIComponent(cmd), {cache: 'no-store'})
			.then(function (r) { return r.json().then(function (j) { return {ok: r.ok, j: j}; }); })
			.then(function (x) {
				status.textContent = x.ok ? (cmd === 'stop' ? 'Stopped.' : 'Moving: ' + cmd.replace('-', ' ') + '…')
					: 'Could not move the lens: ' + (x.j.error || 'unknown error');
			})
			.catch(function () { status.textContent = 'Could not reach the camera.'; });
	}
	function start(cmd) { if (moving !== cmd) { moving = cmd; send(cmd); } }
	function stop() { if (moving !== null) { moving = null; send('stop'); } }

	Array.prototype.forEach.call(document.querySelectorAll('.lens-btn'), function (b) {
		var cmd = b.getAttribute('data-cmd');
		b.addEventListener('pointerdown', function (e) { e.preventDefault(); b.setPointerCapture(e.pointerId); start(cmd); });
		b.addEventListener('pointerup', stop);
		b.addEventListener('pointercancel', stop);
		b.addEventListener('lostpointercapture', stop);
		b.addEventListener('keydown', function (e) { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) { e.preventDefault(); start(cmd); } });
		b.addEventListener('keyup', function (e) { if (e.key === ' ' || e.key === 'Enter') stop(); });
	});
	Array.prototype.forEach.call(document.querySelectorAll('.lens-jog'), function (r) {
		function apply() {
			var v = Number(r.value);
			if (v > 0) start(r.getAttribute('data-pos'));
			else if (v < 0) start(r.getAttribute('data-neg'));
			else stop();
		}
		function release() { r.value = 0; stop(); }
		r.addEventListener('input', apply);
		r.addEventListener('pointerup', release);
		r.addEventListener('pointercancel', release);
		r.addEventListener('touchend', release);
		r.addEventListener('keyup', release);
		r.addEventListener('blur', release);
	});
	document.getElementById('lens-stop').addEventListener('click', function () { moving = null; send('stop'); });

	var keys = {ArrowUp: 'zoom-in', ArrowDown: 'zoom-out', ArrowLeft: 'focus-near', ArrowRight: 'focus-far'};
	document.addEventListener('keydown', function (e) {
		if (keys[e.key] && !e.repeat && !/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) { e.preventDefault(); start(keys[e.key]); }
	});
	document.addEventListener('keyup', function (e) { if (keys[e.key]) stop(); });
	window.addEventListener('blur', stop);
	document.addEventListener('visibilitychange', function () { if (document.hidden) stop(); });
})();
</script>
<%in p/footer.cgi %>
