"""Run every capstone code cell in a fresh Jupyter kernel and save its outputs."""
from pathlib import Path
import os
import sys
import time
from queue import Empty
import nbformat
from jupyter_client import KernelManager

def main():
    root=Path(__file__).resolve().parents[2]
    path=root/'work/notebooks/capstone.ipynb'
    notebook=nbformat.read(path,as_version=4)
    for cell in notebook.cells:
        if cell.cell_type=='code':
            cell.outputs=[]
            cell.execution_count=None
    manager=KernelManager(kernel_name='python3')
    manager.kernel_spec.argv=[sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}']
    env=os.environ.copy()
    env['PYTHONIOENCODING']='utf-8'
    env['MPLBACKEND']='Agg'
    env['PYTHONDONTWRITEBYTECODE']='1'
    manager.start_kernel(cwd=str(root),env=env)
    client=manager.client()
    client.start_channels()
    try:
        client.wait_for_ready(timeout=60)
        count=0
        for index,cell in enumerate(notebook.cells):
            if cell.cell_type!='code':continue
            message_id=client.execute(cell.source,allow_stdin=False,stop_on_error=True)
            deadline=time.monotonic()+(3600 if 'run_warehouse(ROOT)' in cell.source else 600)
            error=None
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError(f'Cell {index} timed out')
                try:message=client.get_iopub_msg(timeout=min(remaining,30))
                except Empty:continue
                if message.get('parent_header',{}).get('msg_id')!=message_id:continue
                kind=message['header']['msg_type'];content=message['content']
                if kind=='execute_input':cell.execution_count=content['execution_count']
                elif kind=='stream':
                    cell.outputs.append(nbformat.v4.new_output('stream',name=content['name'],text=content['text']))
                    if 'run_warehouse(ROOT)' in cell.source and content['name']=='stdout':
                        print(content['text'],end='',flush=True)
                elif kind in ('display_data','execute_result'):
                    args={'data':content['data'],'metadata':content.get('metadata',{})}
                    if kind=='execute_result':args['execution_count']=content['execution_count']
                    cell.outputs.append(nbformat.v4.new_output(kind,**args))
                elif kind=='error':
                    error=content
                    cell.outputs.append(nbformat.v4.new_output('error',ename=content['ename'],evalue=content['evalue'],traceback=content['traceback']))
                elif kind=='clear_output':cell.outputs=[]
                elif kind=='status' and content['execution_state']=='idle':break
            nbformat.write(notebook,path)
            if error:raise RuntimeError(f"Cell {index}: {error['ename']}: {error['evalue']}")
            count+=1
            print(f'Completed code cell {count}',flush=True)
        # Put the freshly computed abstract first for readers opening the saved notebook.
        notebook.cells=[c for c in notebook.cells if not c.metadata.get('capstone_abstract')]
        for cell in notebook.cells:
            for output in cell.get('outputs', []):
                value=output.get('data', {}).get('text/markdown', '')
                if value.startswith('## Abstract (written after the results)'):
                    abstract=nbformat.v4.new_markdown_cell(value.replace('## Abstract (written after the results)', '## Abstract', 1))
                    abstract.metadata['capstone_abstract']=True
                    break
            else:
                continue
            break
        notebook.cells.insert(1, abstract)
        nbformat.write(notebook,path)
        nbformat.validate(notebook)
        assert all(c.execution_count is not None for c in notebook.cells if c.cell_type=='code')
        assert not any(o.output_type=='error' for c in notebook.cells if c.cell_type=='code' for o in c.outputs)
        print(f'PASS: all {count} code cells executed in order in a fresh kernel.',flush=True)
    finally:
        client.stop_channels()
        manager.shutdown_kernel(now=True)

if __name__=='__main__':main()
