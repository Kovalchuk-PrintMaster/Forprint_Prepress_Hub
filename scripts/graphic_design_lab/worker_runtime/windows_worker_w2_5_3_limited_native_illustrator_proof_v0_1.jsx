#target illustrator
/* ForPrint GDL W2.5.3 SYNTHETIC ONLY; no customers, SMB or dialogs.
   NO_DIALOGS_OR_ALERTS. Do not operate on pre-existing document objects. */
(function () {
    var taskId = 'gdl-w253-limited-native-001';
    var outFile = new File('D:/ForPrint_Automation/GraficsDesignLab/Automation/jobs/' +
                           taskId + '/a0001/export/native_probe.ai');
    var fontName = 'ZapfChanceryC';
    var marker = 'FORPRINT W2.5.3 / SYNTHETIC PROOF';
    var mm = 72 / 25.4;
    var oldDoc = null, doc = null, reopened = null;
    var stage = 'INITIALIZE';
    function assertIt(ok, msg) { if (!ok) { throw new Error('W253_' + msg); } }
    try {
        stage = 'ACTIVE_DOCUMENT';
        if (app.documents.length) { oldDoc = app.activeDocument; }
        assertIt(!outFile.exists, 'AI_ALREADY_EXISTS');
        stage = 'FONT_LOOKUP';
        var font = app.textFonts.getByName(fontName);
        assertIt(font && font.name === fontName, 'ZAPF_FONT_MISSING');
        stage = 'CREATE_DOCUMENT';
        doc = app.documents.add(DocumentColorSpace.RGB, 214 * mm, 301 * mm);
        assertIt(doc.artboards.length === 1, 'ARTBOARD_CREATION_FAILED');
        var art = doc.artboards[0].artboardRect;
        var layer = doc.layers[0];
        layer.name = 'ForPrint - Synthetic Native Area Text';
        var shape = layer.pathItems.rectangle(art[1] - 32 * mm,
                                              art[0] + 32 * mm, 150 * mm, 180 * mm);
        shape.filled = false;
        shape.stroked = false;
        stage = 'CREATE_AREA_TEXT';
        var text = layer.textFrames.areaText(shape);
        text.name = 'forprint_w253_synthetic_area_text';
        text.contents = marker;
        text.textRange.characterAttributes.textFont = font;
        text.textRange.characterAttributes.size = 16;
        text.textRange.paragraphAttributes.justification = Justification.CENTER;
        assertIt(text.kind === TextType.AREATEXT, 'AREA_TEXT_NOT_NATIVE');
        stage = 'SAVE_NATIVE_AI';
        var opts = new IllustratorSaveOptions();
        opts.pdfCompatible = true;
        opts.compressed = true;
        doc.saveAs(outFile, opts);
        assertIt(outFile.exists && outFile.length > 1000, 'AI_SAVE_FAILED');
        doc.close(SaveOptions.DONOTSAVECHANGES);
        doc = null;
        stage = 'REOPEN_NATIVE_AI';
        reopened = app.open(outFile);
        assertIt(reopened.artboards.length === 1, 'AI_REOPEN_ARTBOARD_FAILED');
        assertIt(reopened.textFrames.length === 1, 'AI_REOPEN_TEXT_COUNT_FAILED');
        var check = reopened.textFrames.getByName('forprint_w253_synthetic_area_text');
        assertIt(check.kind === TextType.AREATEXT, 'AI_REOPEN_EDITABLE_TEXT_FAILED');
        assertIt(check.contents === marker, 'AI_REOPEN_TEXT_CHANGED');
        assertIt(check.textRange.characterAttributes.textFont.name === fontName,
                 'AI_REOPEN_FONT_CHANGED');
        reopened.close(SaveOptions.DONOTSAVECHANGES);
        reopened = null;
        return 'FORPRINT_NATIVE_AI_REOPENED';
    } catch (e) {
        return 'W253_JSX_FAIL_' + stage;
    } finally {
        if (reopened) { try { reopened.close(SaveOptions.DONOTSAVECHANGES); } catch (_) {} }
        if (doc) { try { doc.close(SaveOptions.DONOTSAVECHANGES); } catch (_) {} }
        if (oldDoc) { try { oldDoc.activate(); } catch (_) {} }
    }
})();
