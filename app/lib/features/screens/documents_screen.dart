import 'package:flutter/material.dart';
import 'package:cambric_design/cambric_design.dart';
import 'dart:io';
import 'package:path_provider/path_provider.dart';

class DocumentsScreen extends StatefulWidget {
  const DocumentsScreen({super.key});

  @override
  State<DocumentsScreen> createState() => _DocumentsScreenState();
}

class _DocumentsScreenState extends State<DocumentsScreen> {
  final TextEditingController _controller = TextEditingController();
  String _template = 'Blank';

  void _insert(String prefix, String suffix) {
    final text = _controller.text;
    final selection = _controller.selection;
    final start = selection.start;
    final end = selection.end;
    if (start < 0 || end < 0) {
      _controller.text = text + prefix + suffix;
      _controller.selection = TextSelection.collapsed(offset: _controller.text.length - suffix.length);
      return;
    }
    final newText = text.substring(0, start) + prefix + text.substring(start, end) + suffix + text.substring(end);
    _controller.text = newText;
    _controller.selection = TextSelection.collapsed(offset: start + prefix.length + (end - start) + suffix.length);
  }

  Future<void> _save() async {
    final dir = await getApplicationDocumentsDirectory();
    final file = File('${dir.path}/c_editor_doc.txt');
    await file.writeAsString(_controller.text);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Saved')));
    }
  }

  Future<void> _load() async {
    final dir = await getApplicationDocumentsDirectory();
    final file = File('${dir.path}/c_editor_doc.txt');
    if (await file.exists()) {
      final text = await file.readAsString();
      setState(() => _controller.text = text);
    }
  }

  @override
  Widget build(BuildContext context) {
    return DsPage(
      title: 'Documents',
      child: Column(
        children: [
          Row(
            children: [
              DropdownButton<String>(
                value: _template,
                items: const [
                  DropdownMenuItem(value: 'Blank', child: Text('Blank')),
                  DropdownMenuItem(value: 'Essay', child: Text('Essay')),
                  DropdownMenuItem(value: 'Report', child: Text('Report')),
                ],
                onChanged: (v) {
                  if (v != null) {
                    setState(() {
                      _template = v;
                      if (v == 'Essay') _controller.text = '# Essay\n\nIntroduction...\n';
                      if (v == 'Report') _controller.text = '# Report\n\n## Summary\n';
                      if (v == 'Blank') _controller.text = '';
                    });
                  }
                },
              ),
              const SizedBox(width: 8),
              IconButton(icon: const Icon(Icons.format_bold), onPressed: () => _insert('**', '**')),
              IconButton(icon: const Icon(Icons.format_italic), onPressed: () => _insert('*', '*')),
              IconButton(icon: const Icon(Icons.title), onPressed: () => _insert('# ', '')),
              const Spacer(),
              IconButton(icon: const Icon(Icons.save), onPressed: _save),
              IconButton(icon: const Icon(Icons.folder_open), onPressed: _load),
            ],
          ),
          const SizedBox(height: Space.sm),
          Expanded(
            child: TextField(
              controller: _controller,
              maxLines: null,
              expands: true,
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                hintText: 'Start typing...',
              ),
            ),
          ),
        ],
      ),
    );
  }
}