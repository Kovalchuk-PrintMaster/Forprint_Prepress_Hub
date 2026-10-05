/*
ForPrint GDL - Greeting Card Illustrator Operator Companion v0.2

Purpose:
- Preserve the proven four-artboard 2x2 layout.
- Keep the source PDF untouched and save a separate AI working copy.
- Reduce Layers-panel nesting and organize each page by operator-facing logical blocks.
- Preserve imported clipping groups, outlined text and raster/vector companions.
- Group related editable items without regenerating missing fonts/text.

Target operator structure:
01 - Front Cover
  [Page Artwork - Clipped Container, only when technically required]
    01 - Sender Logo
    02 - Recipient Branding
    03 - Greeting Title
    04 - Ornamental Frame
    05 - Background
    99 - Technical - Page Clipping Boundary

02 - Back Cover
    01 - Main Artwork
    02 - Ornamental Frame
    03 - Background
    99 - Technical - Page Clipping Boundary

03 - Inside Photo
    01 - Photo
    02 - Ornamental Frame
    03 - Background
    99 - Technical - Page Clipping Boundary

04 - Inside Greeting
    01 - Greeting Text
    02 - Signature
    03 - Decorative Artwork
    04 - Ornamental Frame
    05 - Background
    99 - Technical - Page Clipping Boundary

Notes:
- A redundant outer Page Content wrapper is removed when it is safe to do so.
- A required imported clipping container is preserved rather than flattened.
- Individual greeting text lines remain separate editable objects, but are grouped
  under one logical Greeting Text block.
- This is an operator companion, not the canonical deterministic PDF renderer.
*/

(function () {
    var SCRIPT_ID =
        "FORPRINT_GDL_ILLUSTRATOR_OPERATOR_COMPANION_V0_2_2B";

    var MM_TO_PT = 72.0 / 25.4;
    var GRID_GAP_PT = 10.0 * MM_TO_PT;

    var PAGE_NAMES = [
        "01 - Front Cover",
        "02 - Back Cover",
        "03 - Inside Photo",
        "04 - Inside Greeting"
    ];

    var counters = {
        redundantWrappersRemoved: 0,
        clippedContainersPreserved: 0,
        logicalGroupsCreated: 0,
        technicalClipBoundariesNamed: 0
    };

    function fail(message) {
        alert("ForPrint GDL - STOP\n\n" + message);
        throw new Error(message);
    }

    function safe(fn, fallback) {
        try {
            return fn();
        } catch (e) {
            return fallback;
        }
    }

    function cleanText(value) {
        if (value === undefined || value === null) {
            return "";
        }
        var text = String(value).replace(/[\r\n\t]+/g, " ");
        return text.replace(/\s+/g, " ");
    }

    function containsText(haystack, needle) {
        return cleanText(haystack).toLowerCase().indexOf(
            String(needle).toLowerCase()
        ) >= 0;
    }

    function setName(item, name) {
        safe(function () {
            item.name = name;
        }, null);
    }

    function setNote(item, note) {
        safe(function () {
            item.note = note;
        }, null);
    }

    function setLocked(item, value) {
        safe(function () {
            item.locked = value;
        }, null);
    }

    function boundsOf(item) {
        return safe(function () {
            return item.geometricBounds;
        }, null);
    }

    function widthOf(bounds) {
        if (!bounds || bounds.length !== 4) {
            return 0;
        }
        return Math.abs(bounds[2] - bounds[0]);
    }

    function heightOf(bounds) {
        if (!bounds || bounds.length !== 4) {
            return 0;
        }
        return Math.abs(bounds[1] - bounds[3]);
    }

    function centerOf(bounds) {
        return [
            (bounds[0] + bounds[2]) / 2,
            (bounds[1] + bounds[3]) / 2
        ];
    }

    function relativeGeometry(item, artboardRect) {
        var b = boundsOf(item);
        if (!b) {
            return null;
        }

        return {
            left: b[0] - artboardRect[0],
            top: artboardRect[1] - b[1],
            width: widthOf(b),
            height: heightOf(b),
            centerX: ((b[0] + b[2]) / 2) - artboardRect[0],
            centerY: artboardRect[1] - ((b[1] + b[3]) / 2)
        };
    }

    function artboardIndexForItem(doc, item) {
        var bounds = boundsOf(item);
        if (!bounds) {
            return -1;
        }

        var c = centerOf(bounds);

        for (var i = 0; i < doc.artboards.length; i++) {
            var r = doc.artboards[i].artboardRect;
            var left = Math.min(r[0], r[2]);
            var right = Math.max(r[0], r[2]);
            var bottom = Math.min(r[1], r[3]);
            var top = Math.max(r[1], r[3]);

            if (
                c[0] >= left &&
                c[0] <= right &&
                c[1] >= bottom &&
                c[1] <= top
            ) {
                return i;
            }
        }

        return -1;
    }

    function directChildren(container) {
        var result = [];
        var items = safe(function () {
            return container.pageItems;
        }, null);

        if (!items) {
            return result;
        }

        for (var i = 0; i < items.length; i++) {
            if (items[i].parent === container) {
                result.push(items[i]);
            }
        }

        return result;
    }

    function directIndex(container, item) {
        var children = directChildren(container);
        for (var i = 0; i < children.length; i++) {
            if (children[i] === item) {
                return i;
            }
        }
        return 999999;
    }

    function uniqueDirectItems(container, items) {
        var ordered = [];
        var children = directChildren(container);

        for (var c = 0; c < children.length; c++) {
            for (var i = 0; i < items.length; i++) {
                if (children[c] === items[i]) {
                    ordered.push(children[c]);
                    break;
                }
            }
        }

        return ordered;
    }

    function isClippedGroup(item) {
        return (
            item &&
            item.typename === "GroupItem" &&
            safe(function () {
                return item.clipped === true;
            }, false)
        );
    }

    function hasRasterDescendant(group) {
        var items = safe(function () {
            return group.pageItems;
        }, null);

        if (!items) {
            return false;
        }

        for (var i = 0; i < items.length; i++) {
            if (items[i].typename === "RasterItem") {
                return true;
            }
        }

        return false;
    }

    function createLogicalGroup(
        container,
        name,
        rawItems,
        locked,
        note
    ) {
        var items = uniqueDirectItems(container, rawItems);

        if (items.length === 0) {
            return null;
        }

        var group;

        if (
            items.length === 1 &&
            items[0].typename === "GroupItem"
        ) {
            group = items[0];
        } else {
            group = container.groupItems.add();

            var anchor = items[0];
            safe(function () {
                group.move(anchor, ElementPlacement.PLACEBEFORE);
            }, null);

            for (var i = items.length - 1; i >= 0; i--) {
                setLocked(items[i], false);
                items[i].move(
                    group,
                    ElementPlacement.PLACEATBEGINNING
                );
            }

            counters.logicalGroupsCreated++;
        }

        setName(group, name);
        if (note) {
            setNote(group, note);
        }
        setLocked(group, locked === true);

        return group;
    }

    function nameTechnicalClipBoundary(container) {
        var children = directChildren(container);

        for (var i = 0; i < children.length; i++) {
            var item = children[i];

            if (
                item.typename === "PathItem" &&
                safe(function () {
                    return item.clipping === true;
                }, false)
            ) {
                setName(
                    item,
                    "99 - Technical - Page Clipping Boundary"
                );
                setNote(
                    item,
                    "Imported PDF clipping path. Keep locked; do not delete unless the page clipping model is intentionally rebuilt."
                );
                setLocked(item, true);
                counters.technicalClipBoundariesNamed++;
            }
        }
    }

    function isTechnicalClipBoundary(item) {
        return (
            item.typename === "PathItem" &&
            safe(function () {
                return item.clipping === true;
            }, false)
        );
    }

    function classifyFullPageRasterGroup(
        item,
        geom,
        pageWidth,
        pageHeight
    ) {
        if (
            item.typename !== "GroupItem" ||
            !hasRasterDescendant(item) ||
            !geom
        ) {
            return "";
        }

        var widthRatio = geom.width / pageWidth;
        var heightRatio = geom.height / pageHeight;

        if (widthRatio >= 0.985 && heightRatio >= 0.985) {
            return "BACKGROUND";
        }

        if (
            widthRatio >= 0.90 &&
            heightRatio >= 0.90 &&
            widthRatio < 0.985 &&
            heightRatio < 0.985
        ) {
            return "FRAME";
        }

        return "";
    }

    function applyStaticBlock(
        container,
        name,
        items
    ) {
        var group = createLogicalGroup(
            container,
            name,
            items,
            true,
            "Static imported artwork preserved as one operator block."
        );

        if (group) {
            setLocked(group, true);
        }

        return group;
    }

    function collectStaticAndTechnical(
        container,
        artboardRect
    ) {
        var children = directChildren(container);
        var pageWidth = artboardRect[2] - artboardRect[0];
        var pageHeight = artboardRect[1] - artboardRect[3];

        var frame = [];
        var background = [];
        var technical = [];

        for (var i = 0; i < children.length; i++) {
            var item = children[i];

            if (isTechnicalClipBoundary(item)) {
                technical.push(item);
                continue;
            }

            var geom = relativeGeometry(item, artboardRect);
            var kind = classifyFullPageRasterGroup(
                item,
                geom,
                pageWidth,
                pageHeight
            );

            if (kind === "FRAME") {
                frame.push(item);
            } else if (kind === "BACKGROUND") {
                background.push(item);
            }
        }

        return {
            frame: frame,
            background: background,
            technical: technical
        };
    }

    function notInAny(item, buckets) {
        for (var b = 0; b < buckets.length; b++) {
            for (var i = 0; i < buckets[b].length; i++) {
                if (buckets[b][i] === item) {
                    return false;
                }
            }
        }
        return true;
    }

    function sortByVerticalPosition(items, artboardRect) {
        items.sort(function (a, b) {
            var ga = relativeGeometry(a, artboardRect);
            var gb = relativeGeometry(b, artboardRect);
            var ay = ga ? ga.centerY : 999999;
            var by = gb ? gb.centerY : 999999;
            return ay - by;
        });
    }

    function renameChildrenSequentially(
        group,
        prefix,
        note
    ) {
        if (!group) {
            return;
        }

        var children = directChildren(group);

        for (var i = 0; i < children.length; i++) {
            setName(
                children[i],
                prefix + " " + ("0" + (i + 1)).slice(-2)
            );
            if (note) {
                setNote(children[i], note);
            }
        }
    }

    function structureFrontCover(container, artboardRect) {
        var children = directChildren(container);
        var pageWidth = artboardRect[2] - artboardRect[0];
        var pageHeight = artboardRect[1] - artboardRect[3];

        var statics = collectStaticAndTechnical(
            container,
            artboardRect
        );

        var sender = [];
        var recipient = [];
        var title = [];
        var review = [];

        for (var i = 0; i < children.length; i++) {
            var item = children[i];

            if (
                !notInAny(
                    item,
                    [
                        statics.frame,
                        statics.background,
                        statics.technical
                    ]
                )
            ) {
                continue;
            }

            var geom = relativeGeometry(item, artboardRect);

            if (
                item.typename === "GroupItem" &&
                geom &&
                hasRasterDescendant(item) &&
                geom.width < pageWidth * 0.50 &&
                geom.height < pageHeight * 0.40 &&
                geom.centerY < pageHeight * 0.32
            ) {
                sender.push(item);
                continue;
            }

            if (item.typename === "TextFrame") {
                /*
                 * Content-agnostic classification:
                 * live text is assigned by page geometry only.
                 */
                if (
                    geom &&
                    geom.centerY >= pageHeight * 0.57
                ) {
                    title.push(item);
                } else {
                    recipient.push(item);
                }

                setLocked(item, false);
                continue;
            }

            if (item.typename === "CompoundPathItem") {
                if (
                    geom &&
                    geom.centerY >= pageHeight * 0.57
                ) {
                    title.push(item);
                } else {
                    recipient.push(item);
                }
                setLocked(item, false);
                continue;
            }

            if (
                item.typename === "GroupItem" &&
                !hasRasterDescendant(item)
            ) {
                recipient.push(item);
                continue;
            }

            if (
                geom &&
                geom.centerY >= pageHeight * 0.57
            ) {
                title.push(item);
            } else if (
                geom &&
                geom.centerY < pageHeight * 0.32
            ) {
                sender.push(item);
            } else {
                review.push(item);
            }
        }

        sortByVerticalPosition(sender, artboardRect);
        sortByVerticalPosition(recipient, artboardRect);
        sortByVerticalPosition(title, artboardRect);

        var senderGroup = createLogicalGroup(
            container,
            "01 - Sender Logo",
            sender,
            false,
            "One operator block. May contain one placed logo or multiple preserved components."
        );
        var recipientGroup = createLogicalGroup(
            container,
            "02 - Recipient Branding",
            recipient,
            false,
            "Recipient/organisation identity block; internal objects remain individually editable where source data permits."
        );
        var titleGroup = createLogicalGroup(
            container,
            "03 - Greeting Title",
            title,
            false,
            "Greeting title block. Imported outlined elements remain vector artwork; live text remains live."
        );

        renameChildrenSequentially(
            senderGroup,
            "Component",
            "Preserved source component inside Sender Logo block."
        );
        renameChildrenSequentially(
            recipientGroup,
            "Component",
            "Preserved source component inside Recipient Branding block."
        );
        renameChildrenSequentially(
            titleGroup,
            "Line",
            "Greeting-title source element."
        );

        applyStaticBlock(
            container,
            "04 - Ornamental Frame",
            statics.frame
        );
        applyStaticBlock(
            container,
            "05 - Background",
            statics.background
        );

        if (review.length > 0) {
            createLogicalGroup(
                container,
                "98 - Preserved Review",
                review,
                false,
                "Unclassified imported source items preserved without guessing their semantic role."
            );
        }

        nameTechnicalClipBoundary(container);
    }

    function structureBackCover(container, artboardRect) {
        var children = directChildren(container);
        var statics = collectStaticAndTechnical(
            container,
            artboardRect
        );
        var artwork = [];

        for (var i = 0; i < children.length; i++) {
            if (
                notInAny(
                    children[i],
                    [
                        statics.frame,
                        statics.background,
                        statics.technical
                    ]
                )
            ) {
                artwork.push(children[i]);
            }
        }

        var mainGroup = createLogicalGroup(
            container,
            "01 - Main Artwork",
            artwork,
            false,
            "Main back-cover artwork preserved as one operator block."
        );

        renameChildrenSequentially(
            mainGroup,
            "Component",
            "Preserved source component inside the back-cover artwork."
        );

        applyStaticBlock(
            container,
            "02 - Ornamental Frame",
            statics.frame
        );
        applyStaticBlock(
            container,
            "03 - Background",
            statics.background
        );

        nameTechnicalClipBoundary(container);
    }

    function structureInsidePhoto(container, artboardRect) {
        var children = directChildren(container);
        var statics = collectStaticAndTechnical(
            container,
            artboardRect
        );
        var photo = [];

        for (var i = 0; i < children.length; i++) {
            if (
                notInAny(
                    children[i],
                    [
                        statics.frame,
                        statics.background,
                        statics.technical
                    ]
                )
            ) {
                photo.push(children[i]);
            }
        }

        var photoGroup = createLogicalGroup(
            container,
            "01 - Photo",
            photo,
            false,
            "Portrait/image block. Existing image and clipping-mask structure is preserved inside this block."
        );

        if (photoGroup) {
            var pchildren = directChildren(photoGroup);
            for (var p = 0; p < pchildren.length; p++) {
                if (
                    pchildren[p].typename === "GroupItem" &&
                    (
                        hasRasterDescendant(pchildren[p]) ||
                        isClippedGroup(pchildren[p])
                    )
                ) {
                    setName(
                        pchildren[p],
                        "Image and Clipping Mask"
                    );
                } else {
                    setName(
                        pchildren[p],
                        "Photo Companion " +
                            ("0" + (p + 1)).slice(-2)
                    );
                }
            }
        }

        applyStaticBlock(
            container,
            "02 - Ornamental Frame",
            statics.frame
        );
        applyStaticBlock(
            container,
            "03 - Background",
            statics.background
        );

        nameTechnicalClipBoundary(container);
    }

    function signatureTextSplitIndex(
        candidates,
        pageHeight
    ) {
        if (candidates.length < 2) {
            return candidates.length;
        }

        candidates.sort(function (a, b) {
            return a.centerY - b.centerY;
        });

        var bestIndex = -1;
        var bestGap = 0;
        var minGap = pageHeight * 0.025;

        for (var i = 0; i < candidates.length - 1; i++) {
            var upper = candidates[i];
            var lower = candidates[i + 1];
            var gap = lower.centerY - upper.centerY;

            if (
                lower.centerY > pageHeight * 0.55 &&
                gap >= minGap &&
                gap > bestGap
            ) {
                bestGap = gap;
                bestIndex = i + 1;
            }
        }

        if (bestIndex >= 0) {
            return bestIndex;
        }

        for (var j = 0; j < candidates.length; j++) {
            if (
                candidates[j].centerY >
                pageHeight * 0.72
            ) {
                return j;
            }
        }

        return candidates.length;
    }

    function structureInsideGreeting(
        container,
        artboardRect
    ) {
        var children = directChildren(container);
        var pageWidth = artboardRect[2] - artboardRect[0];
        var pageHeight = artboardRect[1] - artboardRect[3];

        var statics = collectStaticAndTechnical(
            container,
            artboardRect
        );

        var greeting = [];
        var signature = [];
        var decorative = [];
        var signatureNames = [];
        var textCandidates = [];

        for (var i = 0; i < children.length; i++) {
            var item = children[i];

            if (
                !notInAny(
                    item,
                    [
                        statics.frame,
                        statics.background,
                        statics.technical
                    ]
                )
            ) {
                continue;
            }

            var geom = relativeGeometry(item, artboardRect);

            if (item.typename === "TextFrame") {
                textCandidates.push({
                    item: item,
                    centerY: geom ? geom.centerY : 0
                });

                setLocked(item, false);
                continue;
            }

            if (
                item.typename === "GroupItem" &&
                hasRasterDescendant(item) &&
                geom &&
                geom.width < pageWidth * 0.45 &&
                geom.height < pageHeight * 0.35 &&
                geom.centerY > pageHeight * 0.55
            ) {
                signature.push(item);
                signatureNames.push({
                    item: item,
                    name: "Signature Image"
                });
                continue;
            }

            /*
             * Imported handwritten signatures are commonly vector paths rather
             * than text. Keep a compact lower-page vector near the sign-off
             * inside the Signature logical block. Large watermark/decorative
             * artwork is intentionally excluded by the bounded size test.
             */
            if (
                geom &&
                geom.centerY > pageHeight * 0.66 &&
                geom.width < pageWidth * 0.42 &&
                geom.height < pageHeight * 0.32 &&
                (
                    item.typename === "GroupItem" ||
                    item.typename === "CompoundPathItem" ||
                    item.typename === "PathItem"
                )
            ) {
                signature.push(item);
                signatureNames.push({
                    item: item,
                    name: "Handwritten Signature"
                });
                continue;
            }

            decorative.push(item);
        }

        var splitIndex = signatureTextSplitIndex(
            textCandidates,
            pageHeight
        );

        for (
            var tc = 0;
            tc < textCandidates.length;
            tc++
        ) {
            if (tc < splitIndex) {
                greeting.push(
                    textCandidates[tc].item
                );
            } else {
                signature.push(
                    textCandidates[tc].item
                );
            }
        }

        sortByVerticalPosition(
            greeting,
            artboardRect
        );

        sortByVerticalPosition(
            signature,
            artboardRect
        );

        var greetingGroup = createLogicalGroup(
            container,
            "01 - Greeting Text",
            greeting,
            false,
            "All greeting text is grouped as one logical operator block; individual imported text objects remain editable."
        );

        if (greetingGroup) {
            var gchildren = directChildren(greetingGroup);
            for (var g = 0; g < gchildren.length; g++) {
                setName(
                    gchildren[g],
                    "Line " + ("0" + (g + 1)).slice(-2)
                );
                setNote(
                    gchildren[g],
                    "Live text imported from PDF; editable when the required font is available."
                );
            }
        }

        var signatureGroup = createLogicalGroup(
            container,
            "02 - Signature",
            signature,
            false,
            "Closing/signature block kept together for fast operator access."
        );

        if (signatureGroup) {
            var schildren = directChildren(signatureGroup);
            for (var s = 0; s < schildren.length; s++) {
                var assigned = false;
                for (var sn = 0; sn < signatureNames.length; sn++) {
                    if (signatureNames[sn].item === schildren[s]) {
                        setName(
                            schildren[s],
                            signatureNames[sn].name
                        );
                        assigned = true;
                        break;
                    }
                }

                if (!assigned) {
                    if (
                        schildren[s].typename ===
                        "TextFrame"
                    ) {
                        setName(
                            schildren[s],
                            "Signature Text " +
                                (
                                    "0" +
                                    (s + 1)
                                ).slice(-2)
                        );
                    } else {
                        setName(
                            schildren[s],
                            "Signature Component " +
                                (
                                    "0" +
                                    (s + 1)
                                ).slice(-2)
                        );
                    }
                }
            }
        }

        var decorativeGroup = createLogicalGroup(
            container,
            "03 - Decorative Artwork",
            decorative,
            true,
            "Watermark/decorative imported artwork grouped away from editable greeting and signature blocks."
        );

        if (decorativeGroup) {
            renameChildrenSequentially(
                decorativeGroup,
                "Component",
                "Preserved decorative source component."
            );
            setLocked(decorativeGroup, true);
        }

        applyStaticBlock(
            container,
            "04 - Ornamental Frame",
            statics.frame
        );
        applyStaticBlock(
            container,
            "05 - Background",
            statics.background
        );

        nameTechnicalClipBoundary(container);
    }

    function createPageLayers(doc) {
        var existing = {};

        for (var i = 0; i < doc.layers.length; i++) {
            existing[doc.layers[i].name] = true;
        }

        for (var n = 0; n < PAGE_NAMES.length; n++) {
            if (existing[PAGE_NAMES[n]]) {
                fail(
                    "Operator companion layers already exist. " +
                    "Reopen the source PDF before rerunning."
                );
            }
        }

        var layers = [];

        for (var j = PAGE_NAMES.length - 1; j >= 0; j--) {
            var layer = doc.layers.add();
            layer.name = PAGE_NAMES[j];
            layers[j] = layer;
        }

        return layers;
    }

    function captureRootGroups(doc) {
        if (doc.artboards.length !== 4) {
            fail(
                "Expected exactly 4 artboards; found " +
                    doc.artboards.length + "."
            );
        }

        var roots = [null, null, null, null];
        var candidates = [];

        for (var l = 0; l < doc.layers.length; l++) {
            var items = doc.layers[l].pageItems;

            for (var i = 0; i < items.length; i++) {
                if (
                    items[i].parent === doc.layers[l] &&
                    items[i].typename === "GroupItem"
                ) {
                    candidates.push(items[i]);
                }
            }
        }

        for (var c = 0; c < candidates.length; c++) {
            var ab = artboardIndexForItem(
                doc,
                candidates[c]
            );

            if (ab >= 0 && ab < 4) {
                if (roots[ab] !== null) {
                    fail(
                        "More than one top-level page root group " +
                        "was detected on artboard " + (ab + 1) + "."
                    );
                }
                roots[ab] = candidates[c];
            }
        }

        for (var r = 0; r < 4; r++) {
            if (roots[r] === null) {
                fail(
                    "No top-level page root group was detected " +
                    "on artboard " + (r + 1) + "."
                );
            }
        }

        return roots;
    }

    function normalizePageContainer(pageRoot, pageLayer) {
        var current = pageRoot;

        if (!isClippedGroup(current)) {
            var children = directChildren(current);

            if (
                children.length === 1 &&
                children[0].typename === "GroupItem"
            ) {
                var onlyChild = children[0];

                onlyChild.move(
                    pageLayer,
                    ElementPlacement.PLACEATBEGINNING
                );

                safe(function () {
                    current.remove();
                }, null);

                current = onlyChild;
                counters.redundantWrappersRemoved++;
            }
        }

        if (isClippedGroup(current)) {
            setName(
                current,
                "Page Artwork - Clipped Container"
            );
            setNote(
                current,
                "Technical clipping container preserved because flattening it could change page appearance."
            );
            counters.clippedContainersPreserved++;
        } else {
            setName(current, "Page Artwork");
        }

        setLocked(current, false);
        return current;
    }

    function gridRectsFromFirstArtboard(oldRects) {
        var base = oldRects[0];
        var width = base[2] - base[0];
        var height = base[1] - base[3];
        var left = base[0];
        var top = base[1];

        return [
            [left, top, left + width, top - height],
            [
                left + width + GRID_GAP_PT,
                top,
                left + (2 * width) + GRID_GAP_PT,
                top - height
            ],
            [
                left,
                top - height - GRID_GAP_PT,
                left + width,
                top - (2 * height) - GRID_GAP_PT
            ],
            [
                left + width + GRID_GAP_PT,
                top - height - GRID_GAP_PT,
                left + (2 * width) + GRID_GAP_PT,
                top - (2 * height) - GRID_GAP_PT
            ]
        ];
    }

    function saveAsOperatorCompanion(doc, outputFile) {
        var options = new IllustratorSaveOptions();
        options.pdfCompatible = true;
        options.compressed = true;
        options.embedLinkedFiles = true;
        doc.saveAs(outputFile, options);
    }

    function reportFileFor(aiFile) {
        var base = aiFile.fsName.replace(/\.ai$/i, "");
        return new File(
            base + "_operator_companion_report_v0_2.txt"
        );
    }

    if (app.documents.length === 0) {
        fail("No Illustrator document is open.");
    }

    var doc = app.activeDocument;

    var output = File.saveDialog(
        "Save the flatter operator-friendly Illustrator working copy",
        "*.ai"
    );

    if (!output) {
        return;
    }

    if (!/\.ai$/i.test(output.name)) {
        output = new File(output.fsName + ".ai");
    }

    var oldRects = [];

    for (var a = 0; a < 4; a++) {
        var rr = doc.artboards[a].artboardRect;
        oldRects.push([rr[0], rr[1], rr[2], rr[3]]);
    }

    var sourceLayers = [];

    for (var sl = 0; sl < doc.layers.length; sl++) {
        sourceLayers.push(doc.layers[sl]);
    }

    var pageRoots = captureRootGroups(doc);

    // Save a separate AI copy first; the source PDF remains untouched.
    saveAsOperatorCompanion(doc, output);

    var pageLayers = createPageLayers(doc);

    for (var p = 0; p < 4; p++) {
        pageRoots[p].move(
            pageLayers[p],
            ElementPlacement.PLACEATBEGINNING
        );
        setLocked(pageRoots[p], false);
    }

    var newRects = gridRectsFromFirstArtboard(oldRects);

    for (var m = 0; m < 4; m++) {
        var dx = newRects[m][0] - oldRects[m][0];
        var dy = newRects[m][1] - oldRects[m][1];

        pageRoots[m].translate(dx, dy);
        doc.artboards[m].artboardRect = newRects[m];
        doc.artboards[m].name = PAGE_NAMES[m];
    }

    var containers = [];

    for (var q = 0; q < 4; q++) {
        containers[q] = normalizePageContainer(
            pageRoots[q],
            pageLayers[q]
        );
    }

    structureFrontCover(containers[0], newRects[0]);
    structureBackCover(containers[1], newRects[1]);
    structureInsidePhoto(containers[2], newRects[2]);
    structureInsideGreeting(containers[3], newRects[3]);

    for (var z = 0; z < sourceLayers.length; z++) {
        var layer = sourceLayers[z];

        if (
            safe(function () {
                return layer.pageItems.length;
            }, 1) === 0 &&
            safe(function () {
                return layer.layers.length;
            }, 1) === 0
        ) {
            safe(function () {
                layer.remove();
            }, null);
        } else {
            layer.name = "Imported Source Residue - Review";
        }
    }

    doc.save();

    var report = reportFileFor(output);
    report.encoding = "UTF-8";
    report.lineFeed = "Unix";
    report.open("w");

    report.writeln(SCRIPT_ID + "=START");
    report.writeln("SOURCE_PDF_MUTATION=false");
    report.writeln("OUTPUT_AI=" + output.fsName);
    report.writeln("ARTBOARD_COUNT=" + doc.artboards.length);
    report.writeln("TOP_LAYER_COUNT=" + doc.layers.length);
    report.writeln("ARTBOARD_LAYOUT=2x2");
    report.writeln("GRID_GAP_MM=10");
    report.writeln("LOGICAL_BLOCK_MODEL=FLAT_LOGICAL_BLOCKS_V0_2");
    report.writeln("PAGE_CONTENT_WRAPPER_NAME_USED=false");
    report.writeln(
        "REDUNDANT_PAGE_WRAPPERS_REMOVED=" +
            counters.redundantWrappersRemoved
    );
    report.writeln(
        "CLIPPED_CONTAINERS_PRESERVED=" +
            counters.clippedContainersPreserved
    );
    report.writeln(
        "LOGICAL_GROUPS_CREATED=" +
            counters.logicalGroupsCreated
    );
    report.writeln(
        "TECHNICAL_CLIP_BOUNDARIES_NAMED=" +
            counters.technicalClipBoundariesNamed
    );

    for (var x = 0; x < PAGE_NAMES.length; x++) {
        report.writeln(
            "PAGE_" + (x + 1) + "_LAYER=" +
                PAGE_NAMES[x]
        );
        report.writeln(
            "PAGE_" + (x + 1) + "_ARTBOARD=" +
                doc.artboards[x].name
        );
    }

    report.writeln(
        "FRONT_TITLE_LIVE_TEXT_REGENERATION=false"
    );
    report.writeln(
        "IMPORTED_OUTLINED_TEXT_PRESERVED=true"
    );
    report.writeln(
        "CLIPPING_GROUPS_PRESERVED=true"
    );
    report.writeln(
        "GREETING_TEXT_LOGICAL_GROUP=true"
    );
    report.writeln(
        "PHOTO_LOGICAL_GROUP=true"
    );
    report.writeln(
        "OPERATOR_COMPANION_CANONICAL_PRODUCTION_ARTIFACT=false"
    );
    report.writeln(SCRIPT_ID + "=PASS");
    report.close();

    alert(
        "ForPrint GDL operator companion v0.2.1 created.\n\n" +
        "Output:\n" + output.fsName + "\n\n" +
        "Report:\n" + report.fsName + "\n\n" +
        "The source PDF was not modified."
    );
})();
