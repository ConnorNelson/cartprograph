class Map {
    constructor(selector) {
        this.selector = selector;
        this.svg = SVG()
            .addTo(this.selector)
            .viewbox(150, -50, 500, 500)
            .panZoom({
                'zoomMin': 0.5,
                'zoomMax': 10,
            });

        this.nodes = {};
        this.edges = {};

        this.selected = null;

        // function zoom(e) {
        //     e.preventDefault();
        // }
        // this.svg.on('zoom', zoom);
        // this.svg.on('pinchZoomStart', zoom);

        const this_ = this;

        this.svg.on('panning', function (e) {
            const currentBBox = this_.svg.viewbox(),
                  eventBBox = e.detail.box;

            const viewBBox = $(this_.selector)[0].getBoundingClientRect();
            var mapBBox = null;
            Object.entries(this_.nodes).forEach(([_, node]) => {
                mapBBox = mapBBox ? mapBBox.merge(node.group.rbox()) : node.group.rbox();
            });

            var dx = eventBBox.x - currentBBox.x,
                dy = eventBBox.y - currentBBox.y;

            const left = mapBBox.x - viewBBox.left,
                  right = viewBBox.right - mapBBox.x2,
                  top = mapBBox.y - viewBBox.top,
                  bottom = viewBBox.bottom - mapBBox.y2;

            const m = 0; // TODO: figure out margin math

            e.detail.box.x = currentBBox.x;
            e.detail.box.y = currentBBox.y;

            if (dx > 0)
                dx = Math.min(dx, Math.max(left - m, -Math.min(right - m, 0)));
            if (dy > 0)
                dy = Math.min(dy, Math.max(top + m, -Math.min(bottom + m, 0)));
            if (dx < 0)
                dx = -Math.min(-dx, Math.max(right - m, -Math.min(left - m, 0)));
            if (dy < 0)
                dy = -Math.min(-dy, Math.max(bottom + m, -Math.min(top + m, 0)));

            e.detail.box.x += dx;
            e.detail.box.y += dy;
        });

        $(window).keydown(function (e) {
            if (!this_.selected)
                return;

            const s = this_.selected;

            switch(e.code) {

            case 'ArrowLeft':
                if (s instanceof Node && s.parentEdge) {
                    const i = s.parent.children.indexOf(s.parentEdge);
                    if (i > 0)
                        s.parent.children[i-1].node2.select(true, true);
                } else if (s instanceof Edge) {
                    const i = s.node1.children.indexOf(s);
                    if (i > 0)
                        s.node1.children[i-1].select(true, true);
                }
                break;

            case 'ArrowRight':
                if (s instanceof Node && s.parentEdge) {
                    const i = s.parent.children.indexOf(s.parentEdge);
                    if (i < s.parent.children.length - 1)
                        s.parent.children[i+1].node2.select(true, true);
                } else if (s instanceof Edge) {
                    const i = s.node1.children.indexOf(s);
                    if (i < s.node1.children.length - 1)
                        s.node1.children[i+1].select(true, true);
                }
                break;

            case 'ArrowUp':
                if (s instanceof Node && s.parentEdge)
                    s.parentEdge.select(true, true);
                else if (s instanceof Edge)
                    s.node1.select(true, true);
                break;

            case 'ArrowDown':
                if (s instanceof Node && s.children.length)
                    s.children[s.prevSelectedIndex].select(true, true);
                else if (s instanceof Edge)
                    s.node2.select(true, true);
                break;

            case 'Space':
                console.log('space'); // TODO: space should do something
                break;
            }


            if (s.editable) {
                if (e.key.length === 1)
                    s.data.text += e.key;
                switch (e.key) {
                case 'Backspace':
                    s.data.text = s.data.text.slice(0, -1);
                    break;
                case 'Enter':
                    s.data.text += '\n';
                    break;
                }
                s.draw(false);
            }
        });
    }

    pan(x, y) {
        const vbb = this.svg.viewbox();
        this.svg.animate({'when': 'now'}).viewbox(x, y, vbb.w, vbb.h);
    }
}

class Node {
    constructor(map, parent, data, edgeData) {
        this.map = map;
        this.parent = parent;
        this.data = data;
        this.id = data.id;

        this.parentEdge = null;
        this.editable = true;
        this.selected = false;
        this.children = [];
        this.prevSelectedIndex = 0;

        this.map.nodes[this.id] = this;

        this.draw();

        if (parent) {
            this.parentEdge = new Edge(this.map, parent, this, edgeData);
            this.parent.children.push(this.parentEdge);
        }

        this.draw();
    }

    draw(animate=true, recursive=true) {
        if (this.group === undefined) {
            this.group = (this.parent ? this.parent.group.group() : this.map.svg.group());
            this.groupHidden = (this.parent ? this.parent.group.group() : this.map.svg.group());
            this.groupHidden.addClass('hidden');

            this.rectHidden = this.parent === null ? this.groupHidden.circle() : this.groupHidden.rect();
            this.textHidden = this.groupHidden.text('');

            this.rectShadow = (this.parent === null ? this.group.circle() : this.group.rect())
                .addClass('shadow');
            this.rect = (this.parent === null ? this.group.circle() : this.group.rect())
                .addClass('node')
                .click(() => this.select());
            this.text = this.group.text('');
        }

        const prevBB = this.groupHidden.bbox();

        const shadowOffset = 5;

        if (this.parent === null) {
            this.rectShadow
                .attr({
                    'cx': 25 + shadowOffset,
                    'cy': 25 + shadowOffset,
                });
            this.rect
                .attr({
                    'r': 25
                });
            this.rectHidden
                .attr({
                    'r': 25
                });

        } else {
            const this_ = this;
            function text(add) { // TODO: text should not be entirely redrawn every time, its slow
                if (!this_.data)
                    return;
                const strLength = 20;
                const reStr = new RegExp('.{1,' + strLength + '}', 'g')
                const lines = this_.data.text.split(/\r?\n/);
                lines.forEach((line, i) => {
                    if (i > 0 && !lines[i-1])
                        add.tspan('').newLine();
                    if (!line) {
                        return;
                    }
                    const strs = line.match(reStr);
                    strs.forEach((str) => {
                        add.tspan(str)
                            .attr({
                                'text-decoration': 'underline',
                            })
                            .newLine();
                        if (str.length == strLength)
                            add.tspan('\\');
                    });
                });
                if (this_.editable) {
                    const cursor = add.tspan(this_.selected ? '\u25AE' : '\u25AF');
                    if (lines) {
                        const lastLine = lines[lines.length - 1];
                        if (!lastLine || lastLine.length % strLength == 0)
                            cursor.newLine();
                    }
                }
            }

            this.textHidden.text(text);
            const bb = this.textHidden.bbox();
            const m = {
                'x': 10,
                'y': 10,
            };
            const min = {
                'x': 100,
                'y': 100,
            }
            this.rectShadow
                .attr({
                    'x': bb.x - m.x + shadowOffset,
                    'y': bb.y - m.y + shadowOffset,
                    'width': Math.max(bb.w + 2*m.x, min.x),
                    'height': Math.max(bb.h + 2*m.y, min.y),
                });
            this.rect
                .attr({
                    'x': bb.x - m.x,
                    'y': bb.y - m.x,
                    'width': Math.max(bb.w + 2*m.x, min.x),
                    'height': Math.max(bb.h + 2*m.y, min.y),
                });
            this.rectHidden
                .attr({
                    'x': bb.x - m.x,
                    'y': bb.y - m.y,
                    'width': Math.max(bb.w + 2*m.x, min.x),
                    'height': Math.max(bb.h + 2*m.y, min.y),
                });

            this.text.text(text);
        }

        if (this.parent === null) {
            this.x = 0;
            this.y = 0;

        } else {
            const bb = this.parent.rect.bbox();
            const m = 50;

            this.x = 0;
            this.y = bb.h + m;

            var i = this.parent.children.indexOf(this.parentEdge);
            if (i == -1)
                i = this.parent.children.length;
            if (i > 0) {
                const s = this.parent.children[i-1].node2;
                const sbb = s.group.bbox();
                this.x = s.x + sbb.width + m;
            }
        }

        (animate ? this.group.animate({'when': 'now'}) : this.group)
            .transform({
                'translateX': this.x,
                'translateY': this.y,
            });
        this.groupHidden.transform({
            'translateX': this.x,
            'translateY': this.y,
        });

        const curBB = this.groupHidden.bbox();
        var updated = false ||
            (curBB.x !== prevBB.x) ||
            (curBB.y !== prevBB.y) ||
            (curBB.w !== prevBB.w) ||
            (curBB.h !== prevBB.h);
        if (recursive && (updated || recursive === 2)) {
            if (this.parent)
                this.parent.draw(animate, 2);
            if (this.parentEdge)
                this.parentEdge.draw(animate);
            this.children.forEach((edge) => {
                edge.node2.draw(animate, false);
                edge.draw(animate);
            });
        }
    }

    select(selected=true, pan=false) {
        this.selected = selected;
        if (selected) {
            if (this.map.selected && this.map.selected !== this)
                this.map.selected.select(false);
            this.rect.addClass('selected');
            this.map.selected = this;
            if (this.parentEdge) {
                this.parent.prevSelectedIndex = this.parent.children.indexOf(this.parentEdge);
            }
            if (pan) {
                const mbb = $(this.map.selector)[0].getBoundingClientRect(),
                      gbb = this.rect.rbox(),
                      vbb = this.map.svg.viewbox();
                const dx = ((mbb.x + mbb.width/2) - gbb.cx),
                      dy = ((mbb.y + mbb.height/2) - gbb.cy);
                const zoom = Math.min((vbb.h / mbb.height), (vbb.h / mbb.height))
                this.map.pan(vbb.x - dx*zoom, vbb.y - dy*zoom);
            }
        } else {
            this.rect.removeClass('selected');
            this.map.selected = null;
        }
        this.draw(true, false);
    }
}

class Edge {
    constructor(map, node1, node2, data) {
        this.map = map;
        this.node1 = node1;
        this.node2 = node2;
        this.data = data;
        this.id = data.id;

        this.map.edges[this.id] = this;

        this.draw();
    }

    draw(animate=true) {
        const bb1 = this.node1.rect.bbox();
        const bb2 = this.node2.rect.bbox();
        const x1 = bb1.x + bb1.w/2;
        const y1 = bb1.y + bb1.h + 0.5;
        const x2 = this.node2.x + bb2.x + bb2.w/2;
        const y2 = this.node2.y + bb2.y - 0.5;

        const points = [];
        points.push([x1, y1]);
        const t = 50;
        if (Math.abs(x1 - x2) > t) {
            const xm = (x1 + x2) / 2;
            const ym = (y1 + y2) / 2;
            points.push([x1, ym]);
            points.push([x2, ym]);
            points.push([x2, y2]);
        } else {
            points.push([x1, y2]);
            points.push([x1, y2]);
            points.push([x1, y2]);
        }

        if (this.polyline === undefined) {
            this.polyline = this.node1.group.polyline([...Array(points.length)].map((e) => points[0]))
                .addClass('edge')
                .click(() => this.select());
        }
        this.node1.group.front();
        this.node2.group.front();
        (animate ? this.polyline.animate({'when': 'now'}) : this.polyline)
            .plot(points);
    }

    select(selected=true, pan=false) {
        this.selected = selected;
        if (selected) {
            if (this.map.selected)
                this.map.selected.select(false);
            this.polyline.front();
            this.polyline.addClass('selected');
            this.map.selected = this;
            this.node1.prevSelectedIndex = this.node1.children.indexOf(this);
            if (pan) {
                const mbb = $(this.map.selector)[0].getBoundingClientRect(),
                      gbb = this.polyline.rbox(),
                      vbb = this.map.svg.viewbox();
                const dx = ((mbb.x + mbb.width/2) - gbb.cx),
                      dy = ((mbb.y + mbb.height/2) - gbb.cy);
                const zoom = Math.min((vbb.h / mbb.height), (vbb.h / mbb.height))
                this.map.pan(vbb.x - dx*zoom, vbb.y - dy*zoom);
            }
        } else {
            this.polyline.removeClass('selected');
        }
    }
}

$(() => {
    const map = new Map('#map');

    var socket = io();

    socket.on('connect', (e) => {
        $(map.selector + ' > svg').empty();
    });

    socket.on('new_node', (e) => {
        const parent = (e.parent === null) ? null : map.nodes[e.parent];
        new Node(map, parent, e.data, e.edge_data);
    });
});
