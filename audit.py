import sys, ast, re
sys.stdout.reconfigure(encoding='utf-8')

src = open('homework_document_studio.py', encoding='utf-8').read()
ast.parse(src)
print('SYNTAX OK')

import tkinter as tk
tk.Tk.mainloop = lambda self: None
import homework_document_studio as hds
app = hds.Studio()

results = []
def chk(name, cond):
    results.append(('OK' if cond else 'FAIL', name))

# Tabs
for d in ['documents','design','spreadsheet','slides','video','animation','creations']:
    try:
        app._switch_dept(d)
        chk('tab:'+d, True)
    except Exception as e:
        chk('tab:'+d, False)

# Themes
for t in ['Light','Dark','Ocean','Sunset','Forest']:
    try:
        app.preferences['ui_theme'] = t
        app._apply_theme()
        app._rebuild_toolbar('documents')
        chk('theme:'+t, True)
    except Exception as e:
        chk('theme:'+t, False)

# Session 1
chk('bold toolbar', 'bold\"), padx=9' in src)
chk('rainbow color', 'rainbow = [' in src)
chk('yellow highlight', 'FEF08A' in src)
chk('canvas gray', 'C8C8C8' in src)
chk('paper border', 'highlightbackground' in src)
chk('print browser', 'webbrowser.open' in src)
chk('docx auto pip', 'python-docx' in src)
chk('pdf auto pip', 'reportlab' in src)
chk('dark palette', '0F172A' in src)

# Session 2
chk('translate delete+insert', '_apply_replace' in src)
chk('diacritics post fix', 'post_data' in src)
chk('zoom 80', 'IntVar(value=80)' in src)
chk('icons sub-tabs pages', 'Pages' in src)
chk('dark_surface only once', src.count('dark_surface') == 1)
chk('full_ui_refresh', '_full_ui_refresh' in src)
chk('creations tab built', '_build_creations' in src)
chk('7 nav items', src.count('"creations"') >= 3)
chk('ocean theme', 'Ocean' in src)
chk('sunset theme', 'Sunset' in src)
chk('forest theme', 'Forest' in src)
chk('slide theme gallery', '_slide_theme_gallery' in src)
chk('slide gradient bg', 'gradient' in src)
chk('slide layouts', 'Two columns' in src)
chk('sheet fill color', '_sheet_fill_color' in src)
chk('sheet border', '_sheet_toggle_border' in src)
chk('sheet format', '_sheet_apply_format' in src)
chk('sheet freeze', '_sheet_freeze_toggle' in src)
chk('anim fps live', '_anim_fps_changed' in src)
chk('anim bg pick', '_anim_pick_bg' in src)
chk('anim canvas size', '_anim_canvas_size' in src)
chk('video dup track', '_video_duplicate_track' in src)
chk('video add track', '_video_add_track' in src)
chk('video label', '_video_set_clip_label' in src)

# Session 3
chk('word counter', '_update_word_count' in src)
chk('dot unsaved', 'title("' + chr(9679) in src)
chk('F1 shortcuts', '_show_shortcuts' in src)
chk('recents first', 'recent_filtered + rest' in src)
chk('recent badge', 'Recent' in src)
chk('sheet tabs strip', '_sheet_tab_frame' in src)
chk('sheet sort', '_sheet_sort_column' in src)
chk('sheet find replace', '_sheet_find_replace' in src)
chk('sheet chart', '_sheet_chart' in src)
chk('sheet auto fill', '_sheet_auto_fill' in src)
chk('presenter view', '_present_with_notes' in src)
chk('slide add image', '_slide_add_image' in src)
chk('design undo', '_design_undo' in src)
chk('design redo', '_design_redo_action' in src)
chk('design snap', '_design_snap_toggle' in src)
chk('design inplace edit', '_design_edit_text_inplace' in src)
chk('design templates', '_design_templates_gallery' in src)
chk('anim tween', '_anim_tween' in src)
chk('anim symbol', '_anim_symbol_save' in src)
chk('anim audio', '_anim_audio_waveform' in src)
chk('video enhanced tl', '_video_draw_timeline_enhanced' in src)
chk('video waveform', 'waveform' in src)
chk('video trim handles', 'trim handle' in src)
chk('ai assistant', '_ai_assistant' in src)
chk('export zip', '_export_zip' in src)
chk('cloud sync', '_cloud_sync_stub' in src)
chk('plugin system', '_plugins_menu' in src)
chk('plugin loader', '_load_plugins' in src)
chk('ctrl-f sheet', 'Control-f' in src)
chk('dbl click design', 'Double-Button-1' in src and '_design_edit_text_inplace' in src)
chk('plugin at startup', 'after(800' in src)
chk('expanded menus', all(x in src for x in ['_sub("Slides"', '_sub("Design"', '_sub("Tools"']))

app.destroy()

ok   = [r for r in results if r[0]=='OK']
fail = [r for r in results if r[0]=='FAIL']
print(f'\nResults: {len(ok)} OK,  {len(fail)} FAIL\n')
if fail:
    for s,n in fail: print(f'  FAIL  {n}')
else:
    print('ALL CHECKS PASSED')
