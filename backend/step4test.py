python -c "                                                                                                                                            
   import sqlite3                                                                                                                                         
   conn = sqlite3.connect('retirement_planner.db')                                                                                                        
   cursor = conn.cursor()                                                                                                                                 
   cursor.execute('PRAGMA table_info(scenarios)')                                                                                                         
   cols = [row[1] for row in cursor.fetchall()]                                                                                                           
   print('Columns:', cols)                                                                                                                                
   assert 'block_length_years' in cols, 'Missing block_length_years column!'                                                                              
                                                                                                                                                          
   cursor.execute(\"SELECT sql FROM sqlite_master WHERE type='table' AND name='scenarios'\")                                                              
   schema = cursor.fetchone()[0]                                                                                                                          
   assert 'monte_carlo' in schema, 'return_mode check constraint not updated!'                                                                            
   print('✅ Step 4 verified: block_length_years added and return_mode constraint updated.')                                                              
   conn.close()                                                                                                                                           
   "                      