class Map {
    constructor() {
        this.svg = SVG()
            .addTo('#map')
            .viewbox(150, -10, 500, 500)
            .panZoom();

        this.nodes = [];
        this.edges = [];

        this.selected = null;

        this.root = new Node(this, null, '');
        this.root.select();

        // this.svg.on('zoom', (e) => e.preventDefault());
        // this.svg.on('pinchZoomStart', (e) => e.preventDefault());

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

        this.draw();
    }

    draw() {
        if (this.group === undefined) {
            this.group = (this.parent ? this.parent.group.group() : this.map.svg.group());
            this.groupHidden = (this.parent ? this.parent.group.group() : this.map.svg.group());
            this.groupHidden.addClass('hidden');

            if (this.parent === null) {
                this.rect = this.group.circle(50)
                    .addClass('nodeOuter')
                    .click(() => this.select());
                this.groupHidden.circle(50);

            } else {
                const this_ = this;
                function text(add) {
                    this_.data.split(/\r?\n/).forEach((line) => {
                        line.match(/.{1,20}/g).forEach((str, i, a) => {
                            add.tspan(str)
                                .attr({
                                    'text-decoration': 'underline',
                                })
                                .newLine();
                            if (i < a.length - 1)
                                add.tspan('\\');
                        });
                    });
                }

                const textHidden = this.groupHidden.text(text);
                const bb = textHidden.bbox();
                const m = {
                    'x': 10,
                    'y': 10,
                };
                const min = {
                    'x': 100,
                    'y': 100,
                }
                this.rect = this.group.rect(Math.max(bb.w + 2*m.x, min.x), Math.max(bb.h + 2*m.y, min.y))
                    .addClass('nodeOuter')
                    .attr({
                        'x': bb.x - m.x,
                        'y': bb.y - m.y,
                    })
                    .click(() => this.select());
                this.rectInner = this.group.rect(Math.max(bb.w + m.x, min.x - m.x), Math.max(bb.h + m.y, min.y - m.x))
                    .addClass('nodeInner')
                    .attr({
                        'x': bb.x - m.x/2,
                        'y': bb.y - m.y/2,
                    })
                    .click(() => this.select());
                this.groupHidden.rect(Math.max(bb.w + 2*m.x, min.x), Math.max(bb.h + 2*m.y, min.y))
                    .attr({
                        'x': Math.max(bb.x - m.x, min),
                        'y': Math.max(bb.y - m.y, min),
                    });

                this.group.text(text);
            }

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

        this.group.animate().transform({
            'translateX': this.x,
            'translateY': this.y,
        });
        this.groupHidden.transform({
            'translateX': this.x,
            'translateY': this.y,
        });

        if (this.parent !== null && this.parent.parent !== null) {
            this.parent.parent.children.forEach((edge) => {
                edge.node2.draw();
                edge.draw();
            });
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
            if (this.rectInner !== undefined)
                this.rectInner.addClass('selected');
            this.map.selected = this;
            if (this.parentEdge) {
                this.parent.prevSelectedIndex = this.parent.children.indexOf(this.parentEdge);
            }
            if (pan) {
                const mbb = $('#map')[0].getBoundingClientRect(),
                      gbb = this.rect.rbox(),
                      vbb = this.map.svg.viewbox();
                const dx = ((mbb.x + mbb.width/2) - gbb.cx),
                      dy = ((mbb.y + mbb.height/2) - gbb.cy);
                const zoom = Math.min((vbb.h / mbb.height), (vbb.h / mbb.height))
                this.map.pan(vbb.x - dx*zoom, vbb.y - dy*zoom);
            }
        } else {
            this.rect.removeClass('selected');
            if (this.rectInner !== undefined)
                this.rectInner.removeClass('selected');
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

        this.draw();
    }

    draw() {
        const bb1 = this.node1.rect.bbox();
        const bb2 = this.node2.rect.bbox();
        const x1 = bb1.x + bb1.w/2;
        const y1 = bb1.y + bb1.h;
        const x2 = this.node2.x + bb2.x + bb2.w/2;
        const y2 = this.node2.y + bb2.y;

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
        }

        if (this.polyline === undefined) {
            this.polyline = this.node1.group.polyline([...Array(points.length)].map((e) => points[0]))
                .addClass('edgeOuter')
                .click(() => this.select());
            this.polylineInner = this.node1.group.polyline([...Array(points.length)].map((e) => points[0]))
                .addClass('edgeInner')
                .click(() => this.select());
        }
        this.polyline.animate().plot(points);
        this.polylineInner.animate().plot(points);
    }

    select(selected=true, pan=false) {
        this.selected = selected;
        if (selected) {
            if (this.map.selected)
                this.map.selected.select(false);
            this.polyline.front();
            this.polylineInner.front();
            this.polyline.addClass('selected');
            this.polylineInner.addClass('selected');
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
        } else {
            this.polyline.removeClass('selected');
            this.polylineInner.removeClass('selected');
        }
    }
}

$(() => {
    const map = new Map();
    const n1 = map.root.child('test1', 'test');
    const n2 = map.root.child('test2', 'test');
    const n3 = map.root.child('test3', 'test');

    n2.child('test21\nhello world', 'test21');
    n3.child('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'test31');

    setTimeout(() => {
        n2.child('test22', 'test22');
        n1.child('test11', 'test11');
    }, 3000);
});
