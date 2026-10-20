#target illustrator
/*
 ForPrint GC18 native P04 BODY-ONLY laboratory adapter v0.1.
 Generated from an exact accepted Intake task by the project-owned server CLI.
 PRIVATE GENERATED INSTANCE: contains the customer's approved greeting text.
 Not a whole greeting card; no front, portrait, signature, PDF/PNG, production release.
 Refuses overwrites, font substitution, or interaction with an existing document.
 No network, SMB, or remote execution. Must run in interactive Illustrator.
*/
(function () {
    var TASK_ID = __GC18_TASK_ID__;
    var SOURCE_SHA = __GC18_SOURCE_SHA__;
    var GREETING = __GC18_GREETING__;
    var MM = 72 / 25.4;
    var FONT_NAME = 'ZapfChanceryC';
    var AREA_ID = 'page4_greeting_text_area';
    var ACTION_SET = 'AlignTextSet';
    var ACTION_NAME = 'AlignText';
    var PREFIX = 'GC18_' + TASK_ID + '_P04_BodyOnly';
    var doc = null, reopened = null, actionFile = null;
    var actionLoaded = false, outputFolder = null, aiFile = null;
    var report = null, state = 'BLOCKED', error = '';

    function must(c, m) { if (!c) { throw new Error(m); } }
    function pt(mm) { return mm * MM; }
    function reportLine(k, v) { report.push(k + '=' + String(v)); }
    function writeReport() {
        if (!outputFolder || !outputFolder.exists) { return; }
        var path = new File(outputFolder.fsName + '/' + PREFIX + '_result.txt');
        path.encoding = 'UTF-8';
        if (path.exists || !path.open('w')) { return; }
        for (var i = 0; i < report.length; i++) { path.writeln(report[i]); }
        path.close();
    }
    function nativeCenterAction() {
        return [
            '/version 3',
            '/name [ 12', '416c69676e54657874536574', ']',
            '/isOpen 1', '/actionCount 1', '/action-1 {',
            '/name [ 9', '416c69676e54657874', ']',
            '/keyIndex 0', '/colorIndex 0', '/isOpen 1', '/eventCount 1',
            '/event-1 {', '/useRulersIn1stQuadrant 0',
            '/internalName (adobe_frameAlignment)',
            '/localizedName [ 24', '417265612054657874204672616d65416c69676e6d656e74', ']',
            '/isOpen 0', '/isOn 1', '/hasDialog 0', '/parameterCount 1',
            '/parameter-1 {', '/key 1717660782', '/showInPalette 4294967295',
            '/type (integer)', '/value 1', '}', '}', '}'
        ].join('\n') + '\n';
    }
    function proofArea(a, text) {
        must(a.kind === TextType.AREATEXT, 'area_not_native');
        must(Math.abs(a.textPath.width / MM - 150) < 0.35, 'area_width_invalid');
        must(Math.abs(a.textPath.height / MM - 180) < 0.35, 'area_height_invalid');
        must(a.contents === text, 'greeting_text_changed');
    }
    report = [];
    reportLine('SCHEMA', 'GC18_NATIVE_PAGE4_BODY_ONLY_PROOF_V0_1');
    reportLine('TASK_ID', TASK_ID);
    reportLine('SOURCE_SHA256', SOURCE_SHA);
    reportLine('NO_PDF_IMPORT', true);
    reportLine('FULL_CARD_READY', false);
    reportLine('PRODUCTION_READY', false);
    reportLine('PDF_PNG_EXPORTED', false);
    try {
        must(/^gc18-[0-9a-f]{24}$/.test(TASK_ID), 'task_id_invalid');
        must(/^[0-9a-f]{64}$/.test(SOURCE_SHA), 'source_identity_invalid');
        must(GREETING.length > 0, 'greeting_missing');
        // No fallback fonts: the exact Windows installation must be validated.
        var font = app.textFonts.getByName(FONT_NAME);
        must(font && font.name === FONT_NAME, 'required_font_missing');
        outputFolder = new Folder(Folder.myDocuments.fsName + '/ForPrint_GC18_NativeAdapterProof');
        must(outputFolder.exists || outputFolder.create(), 'local_output_folder_unavailable');
        aiFile = new File(outputFolder.fsName + '/' + PREFIX + '.ai');
        var reportFile = new File(outputFolder.fsName + '/' + PREFIX + '_result.txt');
        must(!aiFile.exists && !reportFile.exists, 'already_present_no_overwrite');
        doc = app.documents.add(DocumentColorSpace.RGB, pt(214), pt(301));
        must(doc.artboards.length === 1, 'artboard_count_invalid');
        var rect = doc.artboards[0].artboardRect;
        var layer = doc.layers[0];
        layer.name = 'P04 - Editable Greeting Body - Proof';
        var shape = layer.pathItems.rectangle(rect[1] - pt(32), rect[0] + pt(32), pt(150), pt(180));
        shape.stroked = false; shape.filled = false;
        var area = layer.textFrames.areaText(shape);
        area.name = AREA_ID;
        area.contents = GREETING;
        area.textRange.characterAttributes.textFont = font;
        area.textRange.characterAttributes.size = 16;
        area.textRange.characterAttributes.autoLeading = false;
        area.textRange.characterAttributes.leading = 16 * 8 / 7;
        area.textRange.paragraphAttributes.justification = Justification.CENTER;
        area.textRange.paragraphAttributes.spaceBefore = 0;
        area.textRange.paragraphAttributes.spaceAfter = 0;
        app.redraw();
        proofArea(area, GREETING);
        app.executeMenuCommand('deselectall');
        area.selected = true;
        actionFile = new File(outputFolder.fsName + '/' + PREFIX + '_align.aia');
        must(!actionFile.exists, 'action_file_already_exists');
        actionFile.encoding = 'UTF-8';
        must(actionFile.open('w'), 'action_file_create_failed');
        actionFile.write(nativeCenterAction());
        actionFile.close();
        app.loadAction(actionFile);
        actionLoaded = true;
        app.doScript(ACTION_NAME, ACTION_SET, false);
        app.redraw();
        proofArea(area, GREETING);
        doc.selection = null;
        var saveOptions = new IllustratorSaveOptions();
        saveOptions.pdfCompatible = true;
        saveOptions.compressed = true;
        doc.saveAs(aiFile, saveOptions);
        must(aiFile.exists && aiFile.length > 1000, 'ai_save_failed');
        doc.close(SaveOptions.DONOTSAVECHANGES);
        doc = null;
        reopened = app.open(aiFile);
        must(reopened.artboards.length === 1, 'reopened_artboard_count_invalid');
        var probe = reopened.textFrames.getByName(AREA_ID);
        proofArea(probe, GREETING);
        must(reopened.textFrames.length === 1, 'unexpected_text_frames');
        state = 'PASS_STRUCTURAL_VISUAL_PENDING';
        reportLine('AI_SAVED_AND_REOPENED', true);
        reportLine('EDITABLE_AREATEXT', true);
        reportLine('AREA_MM', '150x180');
        reportLine('NATIVE_VERTICAL_ALIGNMENT_ACTION', true);
        reportLine('SENDER_TEXT_READY', false);
        reportLine('SIGNATURE_READY', false);
        reportLine('VISUAL_REVIEW_REQUIRED', true);
        reportLine('AI_BYTES', aiFile.length);
    } catch (e) {
        error = String(e) + (e && e.line ? ' line=' + e.line : '');
        reportLine('ERROR', error.replace(/[\r\n]+/g, ' '));
        reportLine('VISUAL_REVIEW_REQUIRED', true);
    } finally {
        if (actionLoaded) { try { app.unloadAction(ACTION_SET, ''); } catch (ignored) {} }
        if (actionFile && actionFile.exists) { try { actionFile.remove(); } catch (ignored2) {} }
        report.unshift('STATUS=' + state);
        writeReport();
        if (state === 'BLOCKED' && doc) { try { doc.close(SaveOptions.DONOTSAVECHANGES); } catch (ignored3) {} }
        if (state === 'PASS_STRUCTURAL_VISUAL_PENDING') {
            alert('GC18 P04 body-only native proof saved and reopened. Visual review required.');
        } else {
            alert('GC18 native P04 proof BLOCKED. Inspect the local result file.');
        }
    }
})();
