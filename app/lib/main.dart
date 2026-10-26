import 'package:flutter/material.dart';
import 'package:cambric_design/cambric_design.dart';
import 'features/screens/documents_screen.dart';
import 'features/screens/design_screen.dart';
import 'features/screens/spreadsheet_screen.dart';
import 'features/screens/slides_screen.dart';
import 'features/screens/video_screen.dart';
import 'features/screens/animation_screen.dart';

void main() {
  runApp(const CEditorApp());
}

class CEditorApp extends StatelessWidget {
  const CEditorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'C EDITOR',
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.system,
      home: const CEditorShell(),
    );
  }
}

class CEditorShell extends StatefulWidget {
  const CEditorShell({super.key});

  @override
  State<CEditorShell> createState() => _CEditorShellState();
}

class _CEditorShellState extends State<CEditorShell> {
  int _index = 0;
  final _departments = const [
    'Documents',
    'Design',
    'Spreadsheet',
    'Slides',
    'Video',
    'Animation',
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          NavigationRail(
            selectedIndex: _index,
            onDestinationSelected: (i) => setState(() => _index = i),
            labelType: NavigationRailLabelType.all,
            destinations: _departments
                .map((d) => NavigationRailDestination(
                      icon: const Icon(Icons.folder),
                      label: Text(d),
                    ))
                .toList(),
          ),
          const VerticalDivider(thickness: 1, width: 1),
          Expanded(
            child: _index == 0
                ? const DocumentsScreen()
                : _index == 1
                    ? const DesignScreen()
                    : _index == 2
                        ? const SpreadsheetScreen()
                        : _index == 3
                            ? const SlidesScreen()
                            : _index == 4
                                ? const VideoScreen()
                                : _index == 5
                                    ? const AnimationScreen()
                                    : Center(child: Text('${_departments[_index]} department')),
          ),
        ],
      ),
    );
  }
}