#target illustrator
/* ForPrint GDL W2.7-C1 synthetic native AI candidate ONLY.
   No customer content, no dialogs, no network, no production publishing.
   NO_DIALOGS_OR_ALERTS.
   This source is NOT launch-authorized. Runner must prove Limited token,
   interactive session, stage digest, single-use claim and output binding. */
(function () {
    var marker = 'FORPRINT W27C SYNTHETIC AREA TEXT';
    var fontName = 'ZapfChanceryC';
    var phase = 'START';
    var oldDoc = null;
    var doc = null;
    var reopened = null;
    function ensure(cond, reason) { if (!cond) { throw new Error(reason); } }
    try {
        phase = 'RESOLVE_ATTEMPT';
        var source = new File($.fileName);
        ensure(source.exists && source.name === 'main.jsx', 'SOURCE_NAME');
        var inputDir = source.parent;
        ensure(inputDir.name === 'input', 'INPUT_DIR');
        var attemptDir = inputDir.parent;
        ensure(/^a[0-9]{4}$/.test(attemptDir.name), 'ATTEMPT_ID');
        var taskDir = attemptDir.parent;
        ensure(/^gdl-[a-z0-9-]{1,60}$/.test(taskDir.name), 'TASK_ID');
        ensure(taskDir.parent.name === 'jobs', 'JOBS_DIR');
        var exportDir = new Folder(attemptDir.fsName + '/export');
        ensure(exportDir.exists, 'EXPORT_MISSING');
        var output = new File(exportDir.fsName + '/native_result.ai');
        ensure(!output.exists, 'OUTPUT_EXISTS');
        phase = 'FONT';
        var font = app.textFonts.getByName(fontName);
        ensure(font && font.name === fontName, 'FONT_MISSING');
        if (app.documents.length) { oldDoc = app.activeDocument; }
        phase = 'NEW_DOCUMENT';
        var mm = 72 / 25.4;
        doc = app.documents.add(DocumentColorSpace.RGB, 210 * mm, 297 * mm);
        ensure(doc.artboards.length === 1, 'ARTBOARD_COUNT');
        var layer = doc.layers[0];
        layer.name = 'ForPrint Synthetic W27C Native';
        var a = doc.artboards[0].artboardRect;
        var rect = layer.pathItems.rectangle(a[1] - 30*mm, a[0] + 30*mm, 150*mm, 120*mm);
        rect.filled = false;
        rect.stroked = false;
        var frame = layer.textFrames.areaText(rect);
        frame.name = 'w27c_synthetic_area_text';
        frame.contents = marker;
        frame.textRange.characterAttributes.textFont = font;
        frame.textRange.characterAttributes.size = 18;
        frame.textRange.paragraphAttributes.justification = Justification.CENTER;
        ensure(frame.kind === TextType.AREATEXT, 'NOT_AREA_TEXT');
        phase = 'SAVE_NATIVE';
        var options = new IllustratorSaveOptions();
        options.pdfCompatible = true;
        options.compressed = true;
        doc.saveAs(output, options);
        ensure(output.exists && output.length > 1000, 'SAVE_MISSING');
        doc.close(SaveOptions.DONOTSAVECHANGES);
        doc = null;
        phase = 'REOPEN';
        reopened = app.open(output);
        ensure(reopened.artboards.length === 1, 'REOPEN_ARTBOARD');
        ensure(reopened.textFrames.length === 1, 'REOPEN_FRAME_COUNT');
        var saved = reopened.textFrames.getByName('w27c_synthetic_area_text');
        ensure(saved.kind === TextType.AREATEXT, 'REOPEN_NOT_EDITABLE');
        ensure(saved.contents === marker, 'REOPEN_CONTENT');
        ensure(saved.textRange.characterAttributes.textFont.name === fontName, 'REOPEN_FONT');
        reopened.close(SaveOptions.DONOTSAVECHANGES);
        reopened = null;
        return 'FORPRINT_W27C_SYNTHETIC_NATIVE_REOPENED';
    } catch (error) {
        return 'W27C_JSX_FAIL_' + phase;
    } finally {
        if (reopened) { try { reopened.close(SaveOptions.DONOTSAVECHANGES); } catch (_) {} }
        if (doc) { try { doc.close(SaveOptions.DONOTSAVECHANGES); } catch (_) {} }
        if (oldDoc) { try { oldDoc.activate(); } catch (_) {} }
    }
})();
