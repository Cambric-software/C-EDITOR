import 'package:flutter/material.dart';
import 'package:cambric_design/cambric_design.dart';

class SpreadsheetScreen extends StatefulWidget {
  const SpreadsheetScreen({super.key});

  @override
  State<SpreadsheetScreen> createState() => _SpreadsheetScreenState();
}

class _SpreadsheetScreenState extends State<SpreadsheetScreen> {
  final int rows = 6;
  final int cols = 4;
  final List<List<TextEditingController>> _controllers =
      List.generate(6, (_) => List.generate(4, (_) => TextEditingController()));
  final TextEditingController _formula = TextEditingController();
  String _result = '';

  void _evaluate() {
    final input = _formula.text.trim();
    if (input.startsWith('=SUM(') && input.endsWith(')')) {
      final range = input.substring(5, input.length - 1);
      final parts = range.split(':');
      if (parts.length == 2) {
        final start = _cellRef(parts[0]);
        final end = _cellRef(parts[1]);
        if (start != null && end != null) {
          double sum = 0;
          for (int r = start.$1; r <= end.$1; r++) {
            for (int c = start.$2; c <= end.$2; c++) {
              final val = double.tryParse(_controllers[r][c].text) ?? 0;
              sum += val;
            }
          }
          setState(() => _result = 'Sum: $sum');
          return;
        }
      }
    } else if (input.startsWith('=AVERAGE(') && input.endsWith(')')) {
      final range = input.substring(9, input.length - 1);
      final parts = range.split(':');
      if (parts.length == 2) {
        final start = _cellRef(parts[0]);
        final end = _cellRef(parts[1]);
        if (start != null && end != null) {
          double sum = 0;
          int count = 0;
          for (int r = start.$1; r <= end.$1; r++) {
            for (int c = start.$2; c <= end.$2; c++) {
              final val = double.tryParse(_controllers[r][c].text);
              if (val != null) {
                sum += val;
                count++;
              }
            }
          }
          if (count > 0) {
            setState(() => _result = 'Average: ${sum / count}');
            return;
          }
        }
      }
    }
    setState(() => _result = 'Invalid formula');
  }

  (int, int)? _cellRef(String ref) {
    if (ref.length < 2) return null;
    final col = ref[0].codeUnitAt(0) - 'A'.codeUnitAt(0);
    final row = int.tryParse(ref.substring(1));
    if (col < 0 || col >= cols || row == null || row < 1 || row > rows) return null;
    return (row - 1, col);
  }

  @override
  Widget build(BuildContext context) {
    return DsPage(
      title: 'Spreadsheet',
      child: Column(
        children: [
          TextField(
            controller: _formula,
            decoration: const InputDecoration(
              labelText: 'Formula bar',
              border: OutlineInputBorder(),
              hintText: '=SUM(A1:A3) or =AVERAGE(A1:A3)',
            ),
          ),
          const SizedBox(height: Space.sm),
          ElevatedButton(onPressed: _evaluate, child: const Text('Evaluate')),
          if (_result.isNotEmpty) Text(_result),
          const SizedBox(height: Space.sm),
          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: SingleChildScrollView(
                child: Table(
                  border: TableBorder.all(color: Colors.grey),
                  children: List.generate(rows, (r) {
                    return TableRow(
                      children: List.generate(cols, (c) {
                        return SizedBox(
                          width: 80,
                          child: TextField(
                            controller: _controllers[r][c],
                            decoration: const InputDecoration(
                              border: InputBorder.none,
                              contentPadding: EdgeInsets.all(4),
                            ),
                          ),
                        );
                      }),
                    );
                  }),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}