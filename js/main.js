class Map {
    constructor() {
        this.svg = SVG()
            .addTo('#map')
            .viewbox(-250, -250, 500, 500)
            .panZoom();

        this.nodes = [];
        this.edges = [];

        this.selected = null;

        this.root = new Node(this, null, '');
        this.root.select();

        this.svg.on('zoom', (e) => e.preventDefault());
        this.svg.on('pinchZoomStart', (e) => e.preventDefault());

        const this_ = this;

        this.svg.on('panning', function (e) {
            const currentBBox = this_.svg.viewbox(),
                  eventBBox = e.detail.box;

            const viewBBox = $('#map')[0].getBoundingClientRect();
            var mapBBox = null;
            this_.nodes.forEach((node) => {
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
                }
                else if (s instanceof Edge) {
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
                }
                else if (s instanceof Edge) {
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
            }
        });
    }

    pan(x, y) {
        const vbb = this.svg.viewbox();
        this.svg.animate().viewbox(x, y, vbb.w, vbb.h);
    }
}

class Node {
    constructor(map, parent, data) {
        this.map = map;
        this.parent = parent;
        this.data = data;

        this.parentEdge = null;

        this.selected = false;
        this.children = [];
        this.prevSelectedIndex = 0;

        this.map.nodes.push(this);

        if (parent === null) {
            this.x = 0;
            this.y = 0;

        } else {
            const bb = parent.group.bbox();
            const m = 150;

            if (this.parent.children.length) {
                const s = this.parent.children[this.parent.children.length - 1].node2;
                const sbb = s.group.bbox();
                this.x = s.x + sbb.x + sbb.width + m;
            } else {
                this.x = parent.x + bb.x;
            }

            this.y = parent.y + bb.y + bb.h + m;
        }

        this.group = this.map.svg.group()
            .translate(this.x, this.y);

        if (parent === null) {
            this.rect = this.group.circle(50)
                .click(() => this.select(!this.selected));

        } else {
            this.text = this.group.text(this.data);
            const b = this.text.bbox();
            const m = {
                'x': 50,
                'y': 10,
            };
            this.rect = this.group.rect(b.w + 2*m.x, b.h + 2*m.y)
                .attr({
                    'x': b.x - m.x,
                    'y': b.y - m.y,
                })
                .click(() => this.select(!this.selected));
        }
    }

    child(nodeData, edgeData) {
        const node = new Node(this.map, this, nodeData);
        const edge = new Edge(this.map, this, node, edgeData);
        this.children.push(edge);
        return node;
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
                const mbb = $('#map')[0].getBoundingClientRect(),
                      gbb = this.group.rbox(),
                      vbb = this.map.svg.viewbox();
                const dx = ((mbb.x + mbb.width/2) - gbb.cx),
                      dy = ((mbb.y + mbb.height/2) - gbb.cy);
                const zoom = Math.min((vbb.h / mbb.height), (vbb.h / mbb.height))
                this.map.pan(vbb.x - dx*zoom, vbb.y - dy*zoom);
            }
        }
        else {
            this.rect.removeClass('selected');
            this.map.selected = null;
        }
    }
}

class Edge {
    constructor(map, node1, node2, data) {
        this.map = map;
        this.node1 = node1;
        this.node2 = node2;
        this.data = data;

        this.map.edges.push(this);

        this.node2.parentEdge = this;

        const bb1 = this.node1.group.bbox();
        const bb2 = this.node2.group.bbox();
        const x1 = bb1.x + bb1.w/2 + node1.x;
        const y1 = bb1.y + bb1.h + node1.y;
        const x2 = bb2.x + bb2.w/2 + node2.x;
        const y2 = bb2.y + node2.y;

        const points = [];
        points.push([x1, y1]);
        if (x1 !== x2) {
            const xm = (x1 + x2) / 2;
            const ym = (y1 + y2) / 2;
            points.push([x1, ym]);
            points.push([x2, ym]);
        }
        points.push([x2, y2]);

        this.polyline = this.map.svg.polyline(points)
            .click(() => this.select(!this.selected));
    }

    select(selected=true, pan=false) {
        this.selected = selected;
        if (selected) {
            if (this.map.selected)
                this.map.selected.select(false);
            this.polyline.addClass('selected');
            this.map.selected = this;
            this.node1.prevSelectedIndex = this.node1.children.indexOf(this);
            if (pan) {
                const mbb = $('#map')[0].getBoundingClientRect(),
                      gbb = this.polyline.rbox(),
                      vbb = this.map.svg.viewbox();
                const dx = ((mbb.x + mbb.width/2) - gbb.cx),
                      dy = ((mbb.y + mbb.height/2) - gbb.cy);
                const zoom = Math.min((vbb.h / mbb.height), (vbb.h / mbb.height))
                this.map.pan(vbb.x - dx*zoom, vbb.y - dy*zoom);
            }
        }
        else {
            this.polyline.removeClass('selected');
        }
    }
}

$(() => {
    const map = new Map();
    const n1 = map.root.child('test', 'test');
    const n2 = map.root.child('test2', 'test');
    const n3 = map.root.child('test3', 'test');

    n2.child('fgddg', 'dfgdfgg');
    n2.child('fgddg', 'dfgdfgg');
    n3.child('child', 'child');

});
